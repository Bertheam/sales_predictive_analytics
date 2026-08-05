import numpy as np
import pandas as pd
from django.test import SimpleTestCase

from app.ml.evaluation import calculate_metrics, pinball_loss
from app.ml.time_series import classify_demand, forecast_ets, forecast_tsb


class AdvancedForecastModelTests(SimpleTestCase):
    def test_ets_returns_non_negative_weekly_forecast(self):
        days = np.arange(84)
        values = 20 + 0.04 * days + 4 * np.sin(2 * np.pi * days / 7)
        forecast = forecast_ets(pd.Series(values), 7)
        self.assertEqual(len(forecast), 7)
        self.assertTrue(np.isfinite(forecast).all())
        self.assertTrue((forecast >= 0).all())

    def test_tsb_is_reserved_for_intermittent_demand(self):
        values = pd.Series([0, 0, 8, 0, 0, 0, 5, 0, 0, 7] * 8)
        profile = classify_demand(values)
        forecast = forecast_tsb(values, 7)
        self.assertTrue(profile["is_intermittent"])
        self.assertEqual(profile["label"], "INTERMITTENTE")
        self.assertEqual(len(forecast), 7)
        self.assertTrue((forecast >= 0).all())

    def test_metrics_include_wape_bias_and_pinball_loss(self):
        actual = [10, 20, 30]
        predicted = [12, 18, 33]
        metrics = calculate_metrics(actual, predicted)
        self.assertIn("wape", metrics)
        self.assertIn("bias", metrics)
        self.assertGreaterEqual(pinball_loss(actual, predicted, 0.9), 0)
