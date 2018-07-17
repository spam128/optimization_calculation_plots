from django.test import TestCase
from .models import OptimizationConfiguration, OptimizationCalculation
import pandas as pd
from unittest.mock import patch, Mock, call

from .base_configuration import PlotConfig
from .base_view import OptimizationCalculationBasedPlotView

from rest_framework.test import APIRequestFactory
from django.utils.dateparse import parse_datetime
from pytz import utc

CONFIGURATIONS_PATH = 'optimization_calculation_plots.base_configuration'


def localize_utc(parse_datetime):
    def f(time):
        return utc.localize(parse_datetime(time))

    return f


parse_datetime = localize_utc(parse_datetime)


class TestOptimizationPlotEndPoint(TestCase):
    TIME_FREQUENCE = 'H'
    TIME_ZONE = utc

    def setUp(self):
        self.time_frame = ('2018-01-03 11:00:00', '2018-01-03 15:00:00')
        m = Mock()
        m.start_time = parse_datetime(self.time_frame[0])
        m.end_time = parse_datetime(self.time_frame[1])
        self.optimization_calculation = Mock(return_value=m)
        self.optimizaton_configuration = Mock()
        self.opt_calc_get = OptimizationCalculation.objects.get
        self.opt_conf_get = OptimizationConfiguration.objects.get
        OptimizationCalculation.objects.get = self.optimization_calculation
        OptimizationConfiguration.objects.get = self.optimizaton_configuration

    def tearDown(self):
        OptimizationCalculationBasedPlotView.plots_configs = None
        OptimizationCalculation.objects.get = self.opt_calc_get
        OptimizationConfiguration.objects.get = self.opt_conf_get

    def get_mock_model(self, has_optimization_calculation=True):
        test_model = Mock()
        if not has_optimization_calculation:
            delattr(test_model, 'optimization_calculation')
        else:
            delattr(test_model, 'optimization_configuration')
        return test_model

    def get_plot_config(self, test_model, time_filter, index=[], values=[], labels={}):
        index = index if index else ['source', 'optimization_hour']
        values = values if values else ['pow', ]
        return PlotConfig(
            model=test_model,
            filters={},
            time_filter=time_filter,
            index=index,
            values=values,
            labels=labels
        )

    def get_plot_view(self, plot_configs, is_df_multiindex):
        view = OptimizationCalculationBasedPlotView
        view.plots_configs = plot_configs
        view._is_df_multiindex = Mock(return_value=is_df_multiindex)
        return view

    @staticmethod
    def request_get(view):
        factory = APIRequestFactory()
        request = factory.get('', format='json')
        view2 = view.as_view()
        view2.plots_configs = view.plots_configs
        calculation_id = 2048
        return view2(request, calculation_id=calculation_id)

    def get_date_range(self, time_frame):
        return pd.date_range(start=time_frame[0], end=time_frame[1], freq=self.TIME_FREQUENCE)

    def get_queryset_data(self, date_range, sources=[], values=[]):
        sources = sources if sources else ['source1', 'source2']
        values = values if values else self.generate_plot_values(sources, date_range)
        date_list = date_range.tolist() if hasattr(date_range, 'tolist') else date_range
        return {
            'source': sum([[source] * len(date_range) for source in sources], []),
            'optimization_hour': date_list * len(sources),
            'pow': values
        }

    @staticmethod
    def generate_plot_values(sources, date_range):
        return [i for i in range(len(sources) * len(date_range))]

    def get_expected_response_data(self, values, sources, date_range):
        x = date_range
        response = []
        data_chunk_size = len(x)
        sources_length = len(sources)

        for source_index in range(sources_length):
            data = [{'x': x, 'y': values} for x, values in
                    zip(x, values[source_index * data_chunk_size:(source_index + 1) * data_chunk_size])]

            plot_data = {
                'label': '{} {}'.format(sources[source_index], 'pow'),
                'data': data,
                'unit': ''
            }
            response.append(plot_data)
        return response

    @patch(CONFIGURATIONS_PATH + '.PlotConfig.read_frame')
    def test_config_with_source_and_time_function(self, mock_read_frame):
        time_frame = tuple(parse_datetime(time) for time in self.time_frame)
        sources = ['source1', 'source2']
        date_range = self.get_date_range(time_frame)
        values = self.generate_plot_values(sources, date_range)
        time_filter = ['optimization_hour__range', PlotConfig.opt_calc_filter_range]

        expected_response_data = self.get_expected_response_data(values, sources, date_range)
        queryset_data = self.get_queryset_data(date_range)
        mock_read_frame.return_value = pd.DataFrame(data=queryset_data)

        mock_model = self.get_mock_model()
        plot_config = self.get_plot_config(mock_model, time_filter=time_filter)
        view = self.get_plot_view([plot_config, ], is_df_multiindex=True)

        response = self.request_get(view)

        self.assertEqual(plot_config.filters['optimization_hour__range'], time_frame, 'time frame filter')
        self.assertEqual(response.status_code, 200)

        self.assertEqual(response.data, expected_response_data)

        mock_model.objects.filter().values.assert_called_with('pow', 'source', 'optimization_hour')
        self.assertEqual(mock_model.objects.filter.call_args_list, [call(**plot_config.filters), call()])

    @patch(CONFIGURATIONS_PATH + '.PlotConfig.read_frame')
    def test_without_time_filter_generate_date_range(self, mock_read_frame):
        time_frame = [parse_datetime(time) for time in self.time_frame]
        sources = ['source1', 'source2']
        date_range = self.get_date_range(time_frame)
        values = [123, 234]
        queryset_data = {'source': sources, 'pow': values}
        index = ['source', ]
        expected_response_data = self.get_expected_response_data(sorted(values * len(date_range)), sources, date_range)
        mock_read_frame.return_value = pd.DataFrame(data=queryset_data)

        mock_model = self.get_mock_model(has_optimization_calculation=False)
        plot_config_no_time_filter = self.get_plot_config(mock_model, time_filter=[], index=index)

        view = self.get_plot_view([plot_config_no_time_filter, ], is_df_multiindex=True)

        response = self.request_get(view)

        self.assertNotIn('optimization_hour__range', plot_config_no_time_filter.filters)
        self.assertEqual(mock_model.objects.filter.call_args_list[0], call(**plot_config_no_time_filter.filters),
                         'queryset called without time filter')
        mock_model.objects.filter().values.assert_called_with('pow', 'source')
        self.assertEqual(response.data, expected_response_data)

    @patch(CONFIGURATIONS_PATH + '.PlotConfig.read_frame')
    def test_convert_integer_time_series_to_datetime(self, mock_read_frame):
        time_frame = [parse_datetime(time) for time in self.time_frame]
        sources = ['source1', 'source2']
        date_range = self.get_date_range(time_frame)
        integer_date_range = [i for i in range(self.get_date_range(time_frame).shape[0])]
        values = self.generate_plot_values(sources, date_range)
        time_filter = ['optimization_hour__range', PlotConfig.opt_calc_filter_delta]

        expected_response_data = self.get_expected_response_data(values, sources, date_range)
        queryset_data = self.get_queryset_data(integer_date_range)
        mock_read_frame.return_value = pd.DataFrame(data=queryset_data)

        mock_model = self.get_mock_model(has_optimization_calculation=False)
        mock_model._meta.get_field().get_internal_type.return_value = 'IntegerField'
        plot_config = self.get_plot_config(mock_model, time_filter=time_filter)
        view = self.get_plot_view([plot_config, ], is_df_multiindex=True)

        response = self.request_get(view)

        self.assertEqual(plot_config.filters['optimization_hour__range'], (0, len(integer_date_range)),
                         'time frame filter')
        self.assertEqual(response.status_code, 200)

        self.assertEqual(response.data, expected_response_data)

        mock_model.objects.filter().values.assert_called_with('pow', 'source', 'optimization_hour')
        self.assertEqual(mock_model.objects.filter.call_args_list, [call(**plot_config.filters), call()])

    @patch(CONFIGURATIONS_PATH + '.PlotConfig.read_frame')
    def test_multiple_plots_configs_with_labels(self, mock_read_frame):
        time_frame = [parse_datetime(time) for time in self.time_frame]
        sources = ['source1', 'source2']
        date_range = self.get_date_range(time_frame)
        values = self.generate_plot_values(sources, date_range)
        time_filter = ['optimization_hour__range', PlotConfig.opt_calc_filter_range]
        labels = {'source1': 'label1', 'source2': 'label2'}

        expected_response_data = self.get_expected_response_data(values, sources, date_range)
        expected_response_data += self.get_expected_response_data(values, sources, date_range)
        expected_response_data[2]['label'] = '{} {}'.format(labels['source1'], 'pow')
        expected_response_data[3]['label'] = '{} {}'.format(labels['source2'], 'pow')

        queryset_data = self.get_queryset_data(date_range)
        mock_read_frame.side_effect = pd.DataFrame(data=queryset_data), pd.DataFrame(data=queryset_data)

        mock_model = self.get_mock_model()
        plot_config = self.get_plot_config(mock_model, time_filter=time_filter)
        plot_config2 = self.get_plot_config(mock_model, time_filter=time_filter, labels=labels)
        view = self.get_plot_view([plot_config, plot_config2], is_df_multiindex=True)

        response = self.request_get(view)

        self.assertEqual(response.status_code, 200)

        self.assertEqual(response.data, expected_response_data)

    @patch(CONFIGURATIONS_PATH + '.PlotConfig.read_frame')
    def test_series(self, mock_read_frame):
        time_frame = [parse_datetime(time) for time in self.time_frame]
        date_range = self.get_date_range(time_frame)
        values = [i for i in range(len(date_range))]
        time_filter = ['optimization_hour__range', PlotConfig.opt_calc_filter_range]
        index = ['optimization_hour', ]

        expected_response_data = self.get_expected_response_data(values, ['series', ], date_range)
        queryset_data = {
            'optimization_hour': date_range.tolist(),
            'pow': values
        }
        mock_read_frame.return_value = pd.DataFrame(data=queryset_data)

        mock_model = self.get_mock_model()
        mock_model.__name__ = 'series'
        plot_config = self.get_plot_config(mock_model, time_filter=time_filter, index=index)
        view = self.get_plot_view([plot_config, ], is_df_multiindex=False)

        response = self.request_get(view)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, expected_response_data)
