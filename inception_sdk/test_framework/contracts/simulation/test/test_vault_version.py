# third party
from semantic_version import Version

# inception sdk
from inception_sdk.test_framework.contracts.simulation.utils import (
    SimulationTestCase,
    skipForVaultVersion,
)


class VaultVersionApiTest(SimulationTestCase):
    skip_assertion_msg = "The decorator on this test case should cause it to be skipped."

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

    def test_version(self):
        vaultVersion = self.get_vault_version()
        self.assertIsInstance(vaultVersion.major, int)
        self.assertIsInstance(vaultVersion.minor, int)
        self.assertIsInstance(vaultVersion.patch, int)
        self.assertIsInstance(vaultVersion, Version)
        self.assertGreater(vaultVersion, Version(major=0, minor=0, patch=0))

    @skipForVaultVersion(
        lambda v: v < Version("1000.0.0"), "Test that skipping works for Vault versions < 1000.0.0."
    )
    def test_skip_by_vault_version_below(self):
        self.assertFalse(True, VaultVersionApiTest.skip_assertion_msg)

    @skipForVaultVersion(
        lambda v: v > Version("0.0.0"), "Test that skipping works for Vault versions > 0.0.0."
    )
    def test_skip_by_vault_version_above(self):
        self.assertFalse(True, VaultVersionApiTest.skip_assertion_msg)

    @skipForVaultVersion(
        reason="Test that all versions of Vault can be skipped if the skip condition "
        "is omitted from the decorator."
    )
    def test_skip_for_all_vault_versions(self):
        self.assertFalse(True, VaultVersionApiTest.skip_assertion_msg)
