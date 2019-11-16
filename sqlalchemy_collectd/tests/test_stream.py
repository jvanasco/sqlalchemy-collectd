import unittest

import mock

from .. import protocol
from .. import stream


class BreakIntoValuesTest(unittest.TestCase):
    def _internal_stream_one_element(self, type_instance="sometypeinstance"):
        value = protocol.Values(
            type="my_type_one_element",
            host="somehost",
            plugin="someplugin",
            plugin_instance="someplugininstance",
            type_instance=type_instance,
        )

        data = [
            value.build(time=50, values=[5]),
            value.build(time=55, values=[25]),
            value.build(time=60, values=[11]),
        ]

        return data

    def _external_stream_one_element(self):
        value = protocol.Values(
            type="my_type_one_element",
            host="somehost",
            plugin="someplugin",
            plugin_instance="someplugininstance",
            type_instance="sometypeinstance",
        )

        return [
            value.build(
                time=50, type="count", type_instance="some_val", values=[5]
            ),
            value.build(
                time=55, type="count", type_instance="some_val", values=[25]
            ),
            value.build(
                time=60, type="count", type_instance="some_val", values=[11]
            ),
        ]

    def _internal_stream(self, type_instance="sometypeinstance"):
        value = protocol.Values(
            type="my_type",
            host="somehost",
            plugin="someplugin",
            plugin_instance="someplugininstance",
            type_instance=type_instance,
        )

        data = [
            value.build(time=50, values=[5, 10, 15]),
            value.build(time=55, values=[25, 8, 9]),
            value.build(time=60, values=[11, 7, 12]),
        ]

        return data

    def _external_stream(self):
        value = protocol.Values(
            type="my_type",
            host="somehost",
            plugin="someplugin",
            plugin_instance="someplugininstance",
            type_instance="sometypeinstance",
        )

        return [
            value.build(
                time=50, type="count", type_instance="some_val", values=[5]
            ),
            value.build(
                time=50,
                type="derive",
                type_instance="some_other_val",
                values=[10],
            ),
            value.build(
                time=50,
                type="derive",
                type_instance="some_third_val",
                values=[15],
            ),
            value.build(
                time=55, type="count", type_instance="some_val", values=[25]
            ),
            value.build(
                time=55,
                type="derive",
                type_instance="some_other_val",
                values=[8],
            ),
            value.build(
                time=55,
                type="derive",
                type_instance="some_third_val",
                values=[9],
            ),
            value.build(
                time=60, type="count", type_instance="some_val", values=[11]
            ),
            value.build(
                time=60,
                type="derive",
                type_instance="some_other_val",
                values=[7],
            ),
            value.build(
                time=60,
                type="derive",
                type_instance="some_third_val",
                values=[12],
            ),
        ]

    def test_break_into_values(self):

        type_ = protocol.Type(
            "my_type",
            ("some_val", protocol.VALUE_GAUGE),
            ("some_other_val", protocol.VALUE_DERIVE),
            ("some_third_val", protocol.VALUE_DERIVE),
        )

        data = self._internal_stream()
        translator = stream.StreamTranslator(type_)
        l = []
        for v in data:
            l.extend(translator.break_into_individual_values(v))
        self.assertEqual(l, self._external_stream())

    def test_break_into_values_one_element(self):

        type_ = protocol.Type(
            "my_type_one_element", ("some_val", protocol.VALUE_GAUGE)
        )

        data = self._internal_stream_one_element()
        translator = stream.StreamTranslator(type_)
        l = []
        for v in data:
            l.extend(translator.break_into_individual_values(v))
        self.assertEqual(l, self._external_stream_one_element())

    def test_combine_by_time(self):
        type_ = protocol.Type(
            "my_type",
            ("some_val", protocol.VALUE_GAUGE),
            ("some_other_val", protocol.VALUE_DERIVE),
            ("some_third_val", protocol.VALUE_DERIVE),
        )

        collector = mock.Mock()
        aggregator = stream.StreamTranslator(
            type_
        ).combine_into_grouped_values(collector)

        for v in self._external_stream():
            aggregator.put_values(v)

        # when single-value events are combined back into "internal" types,
        # the "type_instance" value is lost; this is only used to collect
        # the pid up front so is not part of any aggregate data in any case.
        self.assertEqual(
            collector.mock_calls,
            [mock.call(v) for v in self._internal_stream(type_instance=None)],
        )

    def test_combine_by_time_one_element(self):
        type_ = protocol.Type(
            "my_type_one_element", ("some_val", protocol.VALUE_GAUGE)
        )

        collector = mock.Mock()
        aggregator = stream.StreamTranslator(
            type_
        ).combine_into_grouped_values(collector)

        for v in self._external_stream_one_element():
            aggregator.put_values(v)

        # for single-value external elements to internal elements, make
        # sure type_instance is set to None
        self.assertEqual(
            collector.mock_calls,
            [
                mock.call(v)
                for v in self._internal_stream_one_element(type_instance=None)
            ],
        )