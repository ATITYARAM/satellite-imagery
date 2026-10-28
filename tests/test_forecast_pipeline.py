import unittest

from app.domains.forecast_pipeline import forecast_image, run_forecast


class ForecastPipelineTests(unittest.TestCase):
    def test_development_forecasts_are_separate_and_honest(self):
        first = run_forecast(2026, force=True)
        second = run_forecast(2027, force=True)
        self.assertEqual(first["data_mode"], "synthetic_development_preview")
        self.assertFalse(first["scientific_forecast_available"])
        self.assertIn("unavailable", first["model"]["xgboost_regression"])
        self.assertEqual(first["target"], "cross-shore shoreline displacement (m); negative means retreat")
        self.assertNotEqual(first["summary"]["mean_displacement_m"], second["summary"]["mean_displacement_m"])
        self.assertTrue(forecast_image(2026).is_file())
        self.assertTrue(forecast_image(2027).is_file())

    def test_rejects_unsupported_horizon(self):
        with self.assertRaises(ValueError):
            run_forecast(2025)
