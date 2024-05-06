# standard libs
import sys
import time

# third party
from semantic_version import Version

# inception sdk
import inception_sdk.test_framework.endtoend as endtoend
from inception_sdk.test_framework.endtoend import skipForVaultVersion

sys.path.append(".")


contract_template_params = {"denomination": "GBP", "interest_rate": "0.05"}
endtoend.testhandle.CONTRACTS = {
    "contract_module_account": {
        "path": "inception_sdk/test_framework/common/contract_modules_examples"
        "/full_contract_with_shared_function.py",
        "template_params": contract_template_params,
    },
}

endtoend.testhandle.CONTRACT_MODULES = {
    "interest": {
        "path": "inception_sdk/test_framework/common/contract_modules_examples/contract_module.py"
    },
    "module_2": {
        "path": "inception_sdk/test_framework/common/contract_modules_examples/contract_module_2.py"
    },
}


class TestProductContractModuleTest(endtoend.End2Endtest):
    skip_assertion_msg = "The decorator on this test case should cause it to be skipped."

    def setUp(self):
        self._started_at = time.time()

    def tearDown(self):
        self._elapsed_time = time.time() - self._started_at

    def test_contract_modules_are_linked_to_test_product(self):
        """
        Test that the contract modules are uploaded and linked to the contract_module_account
        The framework should upload
        """

        cust_id = endtoend.core_api_helper.create_customer()

        contract_module_account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="contract_module_account",
            status="ACCOUNT_STATUS_OPEN",
        )
        # check account open account
        self.assertEqual("ACCOUNT_STATUS_OPEN", contract_module_account["status"])

        # now check that the smart contract has a module link with the alias 'interest' and
        # 'module_2'
        product_version_id = contract_module_account["product_version_id"]
        contract_module_links = endtoend.core_api_helper.get_smart_contract_module_version_links(
            product_version_id
        )[0]
        module_alias = [
            alias for alias in contract_module_links["alias_to_contract_module_version_id"]
        ]
        self.assertEqual(
            module_alias,
            ["interest", "module_2"],
        )

    def test_version(self):
        vault_version = endtoend.core_api_helper.get_vault_version()
        self.assertGreater(vault_version, Version("0.0.0"))

    @skipForVaultVersion(lambda v: v < Version("1000.0.0"))
    def test_skip_by_vault_version_below(self):
        self.assertFalse(True, TestProductContractModuleTest.skip_assertion_msg)

    @skipForVaultVersion(lambda v: v > Version("0.0.0"))
    def test_skip_by_vault_version_above(self):
        self.assertFalse(True, TestProductContractModuleTest.skip_assertion_msg)
