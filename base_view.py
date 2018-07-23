#!/usr/bin/env python
# -*- coding: utf-8 -*-
from rest_framework.generics import ListAPIView
from collections import namedtuple
from django.http import HttpResponseNotFound, HttpResponseServerError

from CommunicationHubRestApi.models import OptimizationCalculation, OptimizationConfiguration
from CommunicationHubRestApi.serializers import PlotDataSerializer
import logging

log = logging.getLogger(__name__)


class OptimizationCalculationBasedPlotView(ListAPIView):
    """
    Base View for plots based on OptimizationCalculation model
    plots_configs - list of configurations(PlotConfig class)
    """
    plots_configs = None

    def __init__(self, *args, **kwargs):
        self.optimization_calculation = -1
        self._pandas_list = PandasList()
        super().__init__(*args, **kwargs)

    def get(self, request, *args, **kwargs):
        try:
            calculation_id = kwargs.pop('calculation_id')
            self.optimization_calculation = OptimizationCalculation.objects.get(id=calculation_id)
        except KeyError:
            return HttpResponseServerError('No calculation ID given')
        except OptimizationCalculation.DoesNotExist:
            return HttpResponseNotFound('Optimization Calculation with ID {} not found'.format(calculation_id))
        if self.plots_configs:
            opt_calc = OptimizationCalculation.objects.get(id=calculation_id)
            opt_conf = OptimizationConfiguration.objects.get(id=opt_calc.optimization_configuration_id)
            self.plots_configs[0].set_optimization_calc_conf(opt_calc, opt_conf)
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        pd_list = self.get_pd_list()
        for plot in self.plots_configs:
            self.add_plot_by_source_to_pandas_list(plot, pd_list)
        return pd_list

    def add_plot_by_source_to_pandas_list(self, plot, pd_list):
        df = plot.df
        if not self._is_df_multiindex(df):
            pd_list.add_ds(df.loc[:, plot.values[0]], plot.name, unit=plot.unit)
            return
        for source_name, frame in self.group_df_by_index(df):
            frame.index = frame.index.droplevel()
            for value in plot.values:
                label = plot.labels.get(source_name, source_name)
                pd_list.add_ds(frame.loc[:,value], label, unit=plot.unit)

    @staticmethod
    def _is_df_multiindex(df):
        return len(df.index.names) > 1

    @staticmethod
    def group_df_by_index(df):
        return df.groupby(level=0)

    def get_serializer_class(self):
        return PlotDataSerializer

    def get_pd_list(self):
        return self._pandas_list


class PandasList(list):
    """
    Extended list with method add_ds, converting pandas data series into serializable objects
    """

    def add_ds(self, data, label=None, unit=''):
        PandasObj = namedtuple('PandasObj', 'label data unit')
        data_col_name = data.columns[0] if hasattr(data, 'columns') else ''
        data_name = getattr(data, 'name', data_col_name)
        kwargs = {
            'label': data_name if not label else '{} {}'.format(label, data_name),
            'data': [{'x': x, 'y': y} for x, y in zip(data.index, data.values)],
            'unit': unit
        }
        obj = PandasObj(**kwargs)
        self.append(obj)
