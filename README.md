# optimization_optimalization_plots
EndPoint gives data which has foreign key OptimizationCalculation or OptimizationConfiguration models for plots.
Each OptimizationCalculation has time frame

input:
parameter for GET request: OptimizationCalculation id

output format:
list with data sets
```python
    {
        "label": "pow",
        "data": [
            {
                "x": "2018-06-07T09:00:00Z",
                "y": 100
            },
            .
            .
            .
            {
                "x": "2018-06-10T09:00:00Z",
                "y": 3300
             }
    }
```
Create plot configuration which can filter and group data.  

**time_filter** defines which model attribute stores time and how to slice data using it.
**index** - attributes which group data f.e. different plot foreach source
**values** - attributes with values for x-axis
```python
PlotConfig = PlotConfig(
    model=DjangoModel,
    filters={
        'key__in':[1, 2, 3],
    },
    time_filter=['optimization_hour__range', PlotConfig.opt_calc_filter_range],
    index=['source', 'optimization_hour'],
    values=['val_att', ]
)
```
Then add it to view attribute

```python
from .base_view import OptimizationCalculationBasedPlotView

class SomeNewEP(OptimizationCalculationBasedPlotView)
    plots_configs=[]
```

Foreach configuration response creates separate dataset.
At the end add entry to urlpatterns in urls.py
```python
    url(r'^some-new-ep', SomeNewEP.as_view()),
```
