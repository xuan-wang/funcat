# -*- coding: utf-8 -*-
#

from functools import reduce

import warnings
import numpy as np
import talib

from .context import ExecutionContext
from .utils import FormulaException, rolling_window, handle_numpy_warning
from .helper import (
    zig_helper,
)
from .time_series import (
    MarketDataSeries,
    NumericSeries,
    BoolSeries,
    fit_series,
    get_series,
    get_bars,
    ensure_timeseries,
)

warnings.simplefilter(action='ignore', category=FutureWarning)
class OneArgumentSeries(NumericSeries):
    func = talib.MA

    def __init__(self, series, arg):
        if isinstance(series, NumericSeries):
            series = series.series

            try:
                series[series == np.inf] = np.nan

                """
                Higher version TA-Lib may zip the (self, series, arg) into *args,
                use class function here to avoid passing self downstream.
                """
                series = self.__class__.func(series, arg)
            except Exception as e:
                raise FormulaException(e)
        super(OneArgumentSeries, self).__init__(series)
        self.extra_create_kwargs["arg"] = arg


class MovingAverageSeries(OneArgumentSeries):
    """http://www.tadoc.org/indicator/MA.htm"""
    func = talib.MA


class WeightedMovingAverageSeries(OneArgumentSeries):
    """http://www.tadoc.org/indicator/WMA.htm"""
    func = talib.WMA


class ExponentialMovingAverageSeries(OneArgumentSeries):
    """http://www.fmlabs.com/reference/default.htm?url=ExpMA.htm"""
    func = talib.EMA


class StdSeries(OneArgumentSeries):
    func = talib.STDDEV


class TwoArgumentSeries(NumericSeries):
    func = talib.STDDEV

    def __init__(self, series, arg1, arg2):
        if isinstance(series, NumericSeries):
            series = series.series

            try:
                series[series == np.inf] = np.nan
                series = self.__class__.func(series, arg1, arg2)
            except Exception as e:
                raise FormulaException(e)
        super(TwoArgumentSeries, self).__init__(series)
        self.extra_create_kwargs["arg1"] = arg1
        self.extra_create_kwargs["arg2"] = arg2


class SMASeries(TwoArgumentSeries):
    """同花顺专用SMA"""

    def func(series, n, _):
        results = np.nan_to_num(series).copy()
        # FIXME this is very slow
        for i in range(1, len(series)):
            results[i] = ((n - 1) * results[i - 1] + results[i]) / n
        return results


class CCISeries(NumericSeries):
    func = talib.CCI

    def __init__(self, high, low, close):
        if isinstance(high, NumericSeries) and isinstance(low, NumericSeries) and isinstance(close, NumericSeries):
            series0 = high.series
            series1 = low.series
            series2 = close.series

            try:
                series0[series0 == np.inf] = np.nan
                series1[series1 == np.inf] = np.nan
                series2[series2 == np.inf] = np.nan
                series = self.__class__.func(series0, series1, series2)
            except Exception as e:
                raise FormulaException(e)
            super(CCISeries, self).__init__(series)


class SumSeries(NumericSeries):
    """求和"""

    def __init__(self, series, period):
        if isinstance(series, NumericSeries):
            series = series.series
            try:
                series[series == np.inf] = 0
                series[series == -np.inf] = 0
                series = talib.SUM(series, period)
            except Exception as e:
                raise FormulaException(e)
        super(SumSeries, self).__init__(series)
        self.extra_create_kwargs["period"] = period


class AbsSeries(NumericSeries):
    def __init__(self, series):
        if isinstance(series, NumericSeries):
            series = series.series
            try:
                series[series == np.inf] = 0
                series[series == -np.inf] = 0
                series = np.abs(series)
            except Exception as e:
                raise FormulaException(e)
        super(AbsSeries, self).__init__(series)


@handle_numpy_warning
def CrossOver(s1, s2):
    """s1金叉s2
    :param s1:
    :param s2:
    :returns: bool序列
    :rtype: BoolSeries
    """
    s1, s2 = ensure_timeseries(s1), ensure_timeseries(s2)
    series1, series2 = fit_series(s1.series, s2.series)
    cond1 = series1 > series2
    series1, series2 = fit_series(s1[1].series, s2[1].series)
    cond2 = series1 <= series2  # s1[1].series <= s2[1].series
    cond1, cond2 = fit_series(cond1, cond2)
    s = cond1 & cond2
    return BoolSeries(s)


def Ref(s1, n):
    return s1[n]


@handle_numpy_warning
def minimum(s1, s2):
    s1, s2 = ensure_timeseries(s1), ensure_timeseries(s2)
    if len(s1) == 0 or len(s2) == 0:
        raise FormulaException("minimum size == 0")
    series1, series2 = fit_series(s1.series, s2.series)
    s = np.minimum(series1, series2)
    return NumericSeries(s)


@handle_numpy_warning
def maximum(s1, s2):
    s1, s2 = ensure_timeseries(s1), ensure_timeseries(s2)
    if len(s1) == 0 or len(s2) == 0:
        raise FormulaException("maximum size == 0")
    series1, series2 = fit_series(s1.series, s2.series)
    s = np.maximum(series1, series2)
    return NumericSeries(s)


@handle_numpy_warning
def count(cond, n):
    # TODO lazy compute
    series = cond.series
    size = len(cond.series) - n
    try:
        result = np.full(size, 0, dtype=int)
    except ValueError as e:
        raise FormulaException(e)
    for i in range(size - 1, 0, -1):
        s = series[-n:]
        result[i] = len(s[s == True])
        series = series[:-1]
    return NumericSeries(result)


@handle_numpy_warning
def every(cond, n):
    return count(cond, n) == n


@handle_numpy_warning
def hhv(s, n):
    # TODO lazy compute
    series = s.series
    size = len(s.series) - n
    try:
        result = np.full(size, 0, dtype=np.float64)
    except ValueError as e:
        raise FormulaException(e)

    result = np.max(rolling_window(series, n), 1)

    return NumericSeries(result)


@handle_numpy_warning
def llv(s, n):
    # TODO lazy compute
    series = s.series
    size = len(s.series) - n
    try:
        result = np.full(size, 0, dtype=np.float64)
    except ValueError as e:
        raise FormulaException(e)

    result = np.min(rolling_window(series, n), 1)

    return NumericSeries(result)


@handle_numpy_warning
def hhvbars(s, n):
    # TODO lazy compute
    series = s.series
    size = len(s.series) - n
    try:
        result = np.full(size, 0, dtype=np.float64)
    except ValueError as e:
        raise FormulaException(e)

    result = np.argmax(rolling_window(series, n), 1)

    return NumericSeries(result)


@handle_numpy_warning
def llvbars(s, n):
    # TODO lazy compute
    series = s.series
    size = len(s.series) - n
    try:
        result = np.full(size, 0, dtype=np.float64)
    except ValueError as e:
        raise FormulaException(e)

    result = np.argmin(rolling_window(series, n), 1)

    return NumericSeries(result)



@handle_numpy_warning
def iif(condition, true_statement, false_statement):
    series1 = get_series(true_statement)
    series2 = get_series(false_statement)
    cond_series, series1, series2 = fit_series(condition.series, series1, series2)

    series = series2.copy()
    series[cond_series] = series1[cond_series]

    return NumericSeries(series)


@handle_numpy_warning
def ceiling(s):
    series = s.series
    return NumericSeries(np.ceil(series))


@handle_numpy_warning
def const(s):
    if isinstance(s, NumericSeries):
        return NumericSeries(s.series)
    elif isinstance(s, np.ndarray):
        return NumericSeries(s)
    else:
        return NumericSeries(np.array([s]))


@handle_numpy_warning
def drawnull(s):
    pass


@handle_numpy_warning
def zig(s, n):
    series = s.series
    assert isinstance(series, np.ndarray)
    z, _ = zig_helper(series, n)
    return NumericSeries(z)


@handle_numpy_warning
def troughbars(s, n, m):
    series = s.series
    assert isinstance(series, np.ndarray)
    z, peers = zig_helper(series, n)
    z_in_p = [z[i] for i in peers]
    count = 0
    for i in range(len(z_in_p) - 1, 1, -1):
        if count == m:
            return i

        if z_in_p[i] < z_in_p[i - 1]:
            count += 1

    return 0

@handle_numpy_warning
def power2(s, n):
    series = s.series
    assert isinstance(series, np.ndarray)
    return NumericSeries(np.power(series, n))

@handle_numpy_warning
def square_root(s):
    series = s.series
    assert isinstance(series, np.ndarray)
    return NumericSeries(np.sqrt(series))
