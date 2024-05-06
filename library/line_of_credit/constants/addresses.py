# features
import library.features.v4.lending.lending_addresses as lending_addresses

TOTAL = "TOTAL"

# Addresses
TOTAL_EMI = f"{TOTAL}_{lending_addresses.EMI}"
TOTAL_PRINCIPAL = f"{TOTAL}_{lending_addresses.PRINCIPAL}"
TOTAL_ORIGINAL_PRINCIPAL = f"{TOTAL}_ORIGINAL_{lending_addresses.PRINCIPAL}"
TOTAL_PRINCIPAL_DUE = f"{TOTAL}_{lending_addresses.PRINCIPAL_DUE}"
TOTAL_INTEREST_DUE = f"{TOTAL}_{lending_addresses.INTEREST_DUE}"
TOTAL_PRINCIPAL_OVERDUE = f"{TOTAL}_{lending_addresses.PRINCIPAL_OVERDUE}"
TOTAL_INTEREST_OVERDUE = f"{TOTAL}_{lending_addresses.INTEREST_OVERDUE}"
TOTAL_ACCRUED_INTEREST_RECEIVABLE = f"{TOTAL}_{lending_addresses.ACCRUED_INTEREST_RECEIVABLE}"
TOTAL_NON_EMI_ACCRUED_INTEREST_RECEIVABLE = (
    f"{TOTAL}_{lending_addresses.NON_EMI_ACCRUED_INTEREST_RECEIVABLE}"
)
TOTAL_PENALTIES = f"{TOTAL}_{lending_addresses.PENALTIES}"

OUTSTANDING_DEBT_ADDRESSES = [
    TOTAL_PRINCIPAL_OVERDUE,
    TOTAL_INTEREST_OVERDUE,
    TOTAL_PENALTIES,
    TOTAL_PRINCIPAL_DUE,
    TOTAL_INTEREST_DUE,
    TOTAL_PRINCIPAL,
    TOTAL_ACCRUED_INTEREST_RECEIVABLE,
    TOTAL_NON_EMI_ACCRUED_INTEREST_RECEIVABLE,
    # the PENALTIES address on the Line of Credit account is not an aggregated address and is
    # applied directly to the Line of Credit account, but needs repaying nonetheless
    lending_addresses.PENALTIES,
]
