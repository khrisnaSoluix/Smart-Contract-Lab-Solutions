# standard libs
from pathlib import Path

# Contracts
WALLET_CONTRACT = Path("library/wallet/contracts/template/wallet.py")

# Workflows
WALLET_APPLICATION = Path("library/wallet/workflows/wallet_application.yaml")
WALLET_AUTO_TOP_UP_SWITCH = Path("library/wallet/workflows/wallet_auto_top_up_switch.yaml")
WALLET_CLOSURE = Path("library/wallet/workflows/wallet_closure.yaml")

# Flag Definitions
# TODO (INC-8850): Path() not handled by framework for flag definitions
AUTO_TOP_UP_WALLET = "library/wallet/flag_definitions/auto_top_up_wallet.resource.yaml"
