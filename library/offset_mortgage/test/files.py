# standard libs
from pathlib import Path

# library
from library.current_account.test import files as ca_files
from library.mortgage.test import files as mortgage_files
from library.savings_account.test import files as sa_files

# Contracts
OFFSET_MORTGAGE_SUPERVISOR_CONTRACT = Path(
    "library/offset_mortgage/supervisors/template/offset_mortgage.py"
)
MORTGAGE_CONTRACT = mortgage_files.MORTGAGE_CONTRACT
CURRENT_ACCOUNT_CONTRACT = ca_files.CURRENT_ACCOUNT_CONTRACT
SAVINGS_ACCOUNT_CONTRACT = sa_files.SAVINGS_ACCOUNT_CONTRACT
