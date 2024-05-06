# library
import library.line_of_credit.constants.addresses as line_of_credit_addresses

# features
import library.features.v4.lending.lending_addresses as lending_addresses
import library.features.v4.lending.overpayment as overpayment

# inception sdk
from inception_sdk.test_framework.common.balance_helpers import BalanceDimensions

DEFAULT = BalanceDimensions()
INTERNAL_CONTRA = BalanceDimensions(lending_addresses.INTERNAL_CONTRA)

# Debt Management
PRINCIPAL = BalanceDimensions(lending_addresses.PRINCIPAL)
EMI = BalanceDimensions(lending_addresses.EMI)
EMI_PRINCIPAL_EXCESS = BalanceDimensions(overpayment.EMI_PRINCIPAL_EXCESS)
ACCRUED_INTEREST_RECEIVABLE = BalanceDimensions(lending_addresses.ACCRUED_INTEREST_RECEIVABLE)
ACCRUED_EXPECTED_INTEREST = BalanceDimensions(overpayment.ACCRUED_EXPECTED_INTEREST)
PRINCIPAL_DUE = BalanceDimensions(lending_addresses.PRINCIPAL_DUE)
INTEREST_DUE = BalanceDimensions(lending_addresses.INTEREST_DUE)
PRINCIPAL_OVERDUE = BalanceDimensions(lending_addresses.PRINCIPAL_OVERDUE)
INTEREST_OVERDUE = BalanceDimensions(lending_addresses.INTEREST_OVERDUE)
NON_EMI_ACCRUED_INTEREST_RECEIVABLE = BalanceDimensions(
    lending_addresses.NON_EMI_ACCRUED_INTEREST_RECEIVABLE
)
OVERPAYMENT = BalanceDimensions(overpayment.OVERPAYMENT)
OVERPAYMENT_SINCE_PREV_DUE_AMOUNT_CALC_TRACKER = BalanceDimensions(
    overpayment.OVERPAYMENT_SINCE_PREV_DUE_AMOUNT_CALC_TRACKER
)
DUE_CALCULATION_EVENT_COUNTER = BalanceDimensions(lending_addresses.DUE_CALCULATION_EVENT_COUNTER)

# Aggregates
TOTAL_PRINCIPAL = BalanceDimensions(line_of_credit_addresses.TOTAL_PRINCIPAL)
TOTAL_ORIGINAL_PRINCIPAL = BalanceDimensions(line_of_credit_addresses.TOTAL_ORIGINAL_PRINCIPAL)
TOTAL_EMI = BalanceDimensions(line_of_credit_addresses.TOTAL_EMI)
TOTAL_PRINCIPAL_DUE = BalanceDimensions(line_of_credit_addresses.TOTAL_PRINCIPAL_DUE)
TOTAL_INTEREST_DUE = BalanceDimensions(line_of_credit_addresses.TOTAL_INTEREST_DUE)
TOTAL_PRINCIPAL_OVERDUE = BalanceDimensions(line_of_credit_addresses.TOTAL_PRINCIPAL_OVERDUE)
TOTAL_INTEREST_OVERDUE = BalanceDimensions(line_of_credit_addresses.TOTAL_INTEREST_OVERDUE)
TOTAL_ACCRUED_INTEREST_RECEIVABLE = BalanceDimensions(
    line_of_credit_addresses.TOTAL_ACCRUED_INTEREST_RECEIVABLE
)
TOTAL_NON_EMI_ACCRUED_INTEREST_RECEIVABLE = BalanceDimensions(
    line_of_credit_addresses.TOTAL_NON_EMI_ACCRUED_INTEREST_RECEIVABLE
)

# Fees
PENALTIES = BalanceDimensions(lending_addresses.PENALTIES)
TOTAL_PENALTIES = BalanceDimensions(line_of_credit_addresses.TOTAL_PENALTIES)
