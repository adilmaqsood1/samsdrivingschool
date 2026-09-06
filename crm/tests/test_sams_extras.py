from django.test import SimpleTestCase

from crm.templatetags.sams_extras import service_image


class ServiceImageFilterTests(SimpleTestCase):
    def test_beginner_courses_get_the_bde_photo(self):
        for title in ["Beginner Driver Education Program", "BDE Advanced", "G1 Starter"]:
            self.assertEqual(service_image(title), "assets/images/sams/service-bde.jpg")

    def test_road_test_packages_get_the_road_test_photo(self):
        for title in ["G2 Road Test Package", "G Road Test", "G2 Exit Prep"]:
            self.assertEqual(service_image(title), "assets/images/sams/service-roadtest.jpg")

    def test_defensive_and_improvement_courses_get_the_defensive_photo(self):
        for title in ["DDC (Defensive Driving Course)", "DI (Driver Improvement Program)"]:
            self.assertEqual(service_image(title), "assets/images/sams/service-defensive.jpg")

    def test_unknown_title_falls_back_to_a_real_photo(self):
        self.assertEqual(service_image("Something Else"), "assets/images/sams/service-bde.jpg")

    def test_blank_title_does_not_raise(self):
        self.assertTrue(service_image("").endswith(".jpg"))
        self.assertTrue(service_image(None).endswith(".jpg"))
