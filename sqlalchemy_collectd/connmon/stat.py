import threading
import time

from .. import internal_types


class HostProg(object):
    __slots__ = (
        "last_time",
        "hostname",
        "progname",
        "total_checkouts",
        "process_count",
        "connection_count",
        "checkout_count",
        "max_process_count",
        "max_connections",
        "max_checkedout",
        "checkouts_per_second",
        "interval",
    )

    def __init__(self, hostname, progname):
        self.last_time = 0
        self.hostname = hostname
        self.progname = progname

        self.total_checkouts = -1
        self.process_count = 0
        self.connection_count = 0
        self.checkout_count = 0
        self.max_process_count = 0
        self.max_connections = 0
        self.max_checkedout = 0
        self.checkouts_per_second = None
        self.interval = 0

    def last_metric(self, now):
        return now - self.last_time

    def kill_processes(self):
        self.process_count = self.connection_count = self.checkout_count = 0
        self.checkouts_per_second = 0.0

    def update_process_stats(self, stats):
        self.process_count = stats.values[
            internal_types.process_internal.get_stat_index("numprocs")
        ]
        self.max_process_count = max(
            self.process_count, self.max_process_count
        )

    def update_pool_stats(self, stats):
        self.checkout_count = stats.values[
            internal_types.pool_internal.get_stat_index("checkedout")
        ]
        self.max_checkedout = max(self.max_checkedout, self.checkout_count)

        self.connection_count = stats.values[
            internal_types.pool_internal.get_stat_index("connections")
        ]
        self.max_connections = max(self.max_connections, self.connection_count)

    def update_total_stats(self, stats):

        self.interval = interval = stats.interval
        timestamp = stats.time

        total_checkouts = stats.values[
            internal_types.totals_internal.get_stat_index("checkouts")
        ]
        if self.total_checkouts == -1:
            self.total_checkouts = total_checkouts

        if self.last_time == 0:
            self.last_time = timestamp
            self.total_checkouts = total_checkouts
        else:
            time_delta = timestamp - self.last_time
            if (
                time_delta > interval
                and total_checkouts > self.total_checkouts
            ):
                self.checkouts_per_second = (
                    total_checkouts - self.total_checkouts
                ) / time_delta
                self.last_time = timestamp
                self.total_checkouts = total_checkouts


class Stat(object):
    def __init__(self, receiver):
        self.receiver = receiver
        self.host_count = 0
        self.max_host_count = 0
        self.process_count = 0
        self.max_process_count = 0
        self.connection_count = 0
        self.max_connections = 0
        self.checkout_count = 0
        self.max_checkedout = 0
        self.checkouts_per_second = None
        self.hostprogs = {}

    def start(self):
        self.worker = threading.Thread(target=self._update)
        self.worker.daemon = True
        self.worker.start()

    def _get_hostprog(self, hostname, progname, hostprogs_seen):
        if (hostname, progname) not in self.hostprogs:
            self.hostprogs[(hostname, progname)] = hostprog = HostProg(
                hostname, progname
            )
        else:
            hostprog = self.hostprogs[(hostname, progname)]
        hostprogs_seen.add((hostname, progname))
        return hostprog

    def _update(self):

        while True:
            time.sleep(1)

            now = time.time()
            timestamp = now
            hostprogs_seen = set()

            for values_obj in self.receiver.get_stats_by_progname(
                "sqlalchemy_totals", timestamp
            ):
                hostname = values_obj.host
                progname = values_obj.plugin_instance

                # TODO: this is awkward, also do we want more per-host
                # style displays.   do we want to not send host from the
                # other end, or filter, or what.
                if progname == "host":
                    continue

                hostprog = self._get_hostprog(
                    hostname, progname, hostprogs_seen
                )
                hostprog.update_total_stats(values_obj)

            for values_obj in self.receiver.get_stats_by_progname(
                "sqlalchemy_pool", timestamp
            ):
                hostname = values_obj.host
                progname = values_obj.plugin_instance

                if progname == "host":
                    continue

                hostprog = self._get_hostprog(
                    hostname, progname, hostprogs_seen
                )

                hostprog.update_pool_stats(values_obj)

            for values_obj in self.receiver.get_stats_by_progname(
                "sqlalchemy_process", timestamp
            ):
                hostname = values_obj.host
                progname = values_obj.plugin_instance
                if progname == "host":
                    continue

                hostprog = self._get_hostprog(
                    hostname, progname, hostprogs_seen
                )

                hostprog.update_process_stats(values_obj)

            for hostprog in list(self.hostprogs.values()):
                if (
                    hostprog.hostname,
                    hostprog.progname,
                ) not in hostprogs_seen:
                    if hostprog.interval is None:
                        continue

                    age = now - hostprog.last_time

                    if age > hostprog.interval * 5:
                        del self.hostprogs[
                            (hostprog.hostname, hostprog.progname)
                        ]
                    elif age > hostprog.interval:
                        hostprog.kill_processes()

            self.update_host_stats()

    def update_host_stats(self):
        self.host_count = len(set(host for (host, prog) in self.hostprogs))
        self.process_count = sum(
            hostprog.process_count for hostprog in self.hostprogs.values()
        )
        self.connection_count = sum(
            hostprog.connection_count for hostprog in self.hostprogs.values()
        )
        self.checkout_count = sum(
            hostprog.checkout_count for hostprog in self.hostprogs.values()
        )
        self.checkouts_per_second = sum(
            hostprog.checkouts_per_second
            for hostprog in self.hostprogs.values()
            if hostprog.checkouts_per_second is not None
        )

        self.max_host_count = max(self.max_host_count, self.host_count)
        self.max_process_count = max(
            self.max_process_count, self.process_count
        )
        self.max_checkedout = max(self.max_checkedout, self.checkout_count)
        self.max_connections = max(self.max_connections, self.connection_count)
