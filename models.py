from django.db import models


class OptimizationConfiguration(models.Model):
    name = models.TextField(default='default configuration')


class OptimizationCalculation(models.Model):
    optimization_configuration = models.ForeignKey(OptimizationConfiguration, related_name='optimization_calculation',
                                                   on_delete=models.CASCADE)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
