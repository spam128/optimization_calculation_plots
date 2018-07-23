#!/usr/bin/env python
# -*- coding: utf-8 -*-
from datetime import timedelta
from .plot_utils import read_frame
import pandas as pd


class PlotConfig:
    """
  Storage for configurations with dynamic generation of DataFrame and queryset for given settings

  input:
  model = model to plot with ForeignKey OptimizationConfiguration or OptimizationCalculation
  filters = additional queryset filters
  index = pandas group data by given list of attributes, order is important check pandas.DataFrame.set_index reference
  values = model attributes for y-axis
  time_filter = time attribute name and time function used to generate time frame filter
  labels = map source_name -> user given name
  """
    optimization_configuration = None
    optimization_calculation = None

    TIME_FREQUENCE = 'H'

    def __init__(self, model, filters, time_filter, index=[], values=[], labels={}, unit=''):
        self._model = model
        self.filters = filters
        self.index = index
        self.values = values
        if time_filter:
            self.time_filter = time_filter[0]
            self.get_time = time_filter[1]
            find_index = self.time_filter.find('__')
            self.time_field = self.time_filter[:find_index] if find_index > -1 else self.time_filter
        self.labels = labels
        self.unit = unit

    @property
    def all_values(self):
        return self.values + self.index

    @classmethod
    def set_optimization_calc_conf(cls, opt_calc, opt_conf):
        cls.optimization_calculation = opt_calc
        cls.optimization_configuration = opt_conf

    @property
    def name(self):
        return self._model.__name__

    @property
    def df(self):
        if hasattr(self, '_df'):
            return self._df
        df = self.read_frame(self.queryset)
        if hasattr(self, 'time_field') and self._get_field_type(self.time_field) == 'IntegerField':
            self._convert_integer_time_series_to_datetime(df)
        if not hasattr(self, 'time_field'):
            return self._generate_date_range(df)
        self._encode_dataframe_index(df)
        df.set_index(self.index, inplace=True)
        return df

    @df.setter
    def df(self, df_value):
        self._df = df_value

    @df.deleter
    def df(self):
        del self._df

    @staticmethod
    def read_frame(queryset):
        return read_frame(queryset)

    @property
    def queryset(self):
        self._set_time_filter(self.optimization_calculation.start_time, self.optimization_calculation.end_time)

        if hasattr(self._model, 'optimization_calculation'):
            self.filters['optimization_calculation'] = self.optimization_calculation.id

        if hasattr(self._model, 'optimization_configuration'):
            self.filters['optimization_configuration'] = self.optimization_configuration.id

        return self._model.objects.filter(**self.filters).values(*self.all_values).order_by(*self.index)

    def _set_time_filter(self, start_time=0, end_time=0):
        if not hasattr(self, 'time_filter'):
            return
        self.filters[self.time_filter] = self.get_time(start_time, end_time)

    def _get_field_type(self, field):
        return self._model._meta.get_field(field).get_internal_type()

    def _convert_integer_time_series_to_datetime(self, df):
        convert_int_to_datetime = lambda x: timedelta(hours=x) + self.optimization_calculation.start_time
        df.loc[:, self.time_field] = df.loc[:, self.time_field].apply(convert_int_to_datetime)

    def _generate_date_range(self, df):
        df.set_index(self.index, inplace=True)

        start_time = self.optimization_calculation.start_time
        end_time = self.optimization_calculation.end_time
        rng = pd.date_range(start=start_time, end=end_time, freq=self.TIME_FREQUENCE).to_pydatetime()
        index = pd.MultiIndex.from_product([df.index, rng])

        date_range = pd.DataFrame(columns=self.values, index=index)
        self._set_values_foreach_date_range_group(date_range, df)

        return date_range

    def _encode_dataframe_index(self, df):
        for index in self.index:
            series = df.loc[:, index]
            if hasattr(series, 'str') and not hasattr(series.str, 'decode'):
                df.loc[:, index] = series.str.encode('utf-8')

    def _set_values_foreach_date_range_group(self, date_range, df):
        for index in df.index:
            date_range.loc[index] = df.loc[index].iloc[0]

    @staticmethod
    def opt_calc_filter_delta(start_time, end_time):
        """ when time is datetimefield """
        time_delta = end_time - start_time
        return 0, int(time_delta.days * 24 + time_delta.seconds / 3600) + 1

    @staticmethod
    def opt_calc_filter_range(start_time, end_time):
        """ when time is integerfield """
        return start_time, end_time
