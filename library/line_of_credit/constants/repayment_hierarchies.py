import library.line_of_credit.constants.addresses as address

REPAYMENT_HIERARCHY = [
    [address.PRINCIPAL_OVERDUE],
    [address.INTEREST_OVERDUE],
    [address.PENALTIES],
    [address.PRINCIPAL_DUE],
    [address.INTEREST_DUE],
]

# Overpayments and early repayments are treated identically from a hierarchy perspective
OVERPAYMENT_HIERARCHY_DELTA = [[address.PRINCIPAL, address.ACCRUED_INTEREST_RECEIVABLE]]
OVERPAYMENT_HIERARCHY = REPAYMENT_HIERARCHY + OVERPAYMENT_HIERARCHY_DELTA

# Useful to retrieve totals without having to distribute amounts
FLATTENED_REPAYMENT_HIERARCHY = [
    address for address_list in REPAYMENT_HIERARCHY for address in address_list
]
FLATTENED_OVERPAYMENT_HIERARCHY = [
    address for address_list in OVERPAYMENT_HIERARCHY for address in address_list
]
