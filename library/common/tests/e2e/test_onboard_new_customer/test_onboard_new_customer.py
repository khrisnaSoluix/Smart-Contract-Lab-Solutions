# Copyright @ 2020 Thought Machine Group Limited. All rights reserved.
import inception_sdk.test_framework.endtoend as endtoend
import time
import unittest

endtoend.testhandle.WORKFLOWS = {
    "ONBOARD_NEW_CUSTOMER": "library/common/workflows/onboard_new_customer.yaml",
}


class InceptionRegressionTest(endtoend.End2Endtest):
    def setUp(self):
        self._started_at = time.time()

    def tearDown(self):
        self._elapsed_time = time.time() - self._started_at
        # Uncomment this for timing info.
        # print('\n{} ({}s)'.format(self.id().rpartition('.')[2], round(self._elapsed_time, 2)))

    @unittest.skip("Unable to automate document uploading")
    def test_onboard_customer_wf(self):
        """
        Using the ONBOARD_NEW_CUSTOMER workflow, ensure a customer can be
        successfully onboarded.
        """
        wf_id = endtoend.workflows_helper.start_workflow("ONBOARD_NEW_CUSTOMER", context={})

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="request_customer_details",
            event_name="customer_details_given",
            context={
                "first_name": "TestWF",
                "last_name": "E2e",
                "date_of_birth": "1950-01-01",
                "mobile_phone_number": "01234567890",
                "home_phone_number": "09876543210",
                "contact_method": "3",
                "email": "test@tester.com",
                "country_of_residence": "GB",
            },
        )
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="request_customer_address",
            event_name="customer_address_given",
            context={
                "postal_area": "SW1A 1AA",
                "street": "The Mall",
                "city": "London",
                "local_municipality": "London",
                "street_number": "1",
                "governing_district": "London",
                "county": "London",
                "town": "London",
                "house_name": "The Palace",
                "effective_from": "2000-01-01",
            },
        )

        # UPLOAD DOCUMENTS
        input("wait")

        endtoend.workflows_helper.wait_for_state(wf_id, "customer_onboarded")
        cust_id = endtoend.workflows_helper.get_global_context(wf_id)["user_id"]

        customer = endtoend.core_api_helper.get_customer(cust_id)

        self.assertEqual(customer["status"], "CUSTOMER_STATUS_ACTIVE")


if __name__ == "__main__":
    endtoend.runtests()
