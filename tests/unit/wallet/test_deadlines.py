from datetime import date

import pytest

from proofkit.contracts import Member
from proofkit.wallet import compute_deadlines, load_wallet_rules


@pytest.mark.parametrize("renewal, n, months, due", [
    (date(2027, 3, 20), 1, ["2027-02"], date(2027, 3, 6)),
    (date(2027, 2, 10), 3, ["2026-11", "2026-12", "2027-01"], date(2027, 1, 27)),  # year rollover, buffer crosses month
    (date(2027, 3, 31), 2, ["2027-01", "2027-02"], date(2027, 3, 17)),             # month-end renewal
    (date(2028, 3, 1), 1, ["2028-02"], date(2028, 2, 16)),                         # leap year
])
def test_deadline_table(wallet_rules_path, renewal, n, months, due):
    rules = load_wallet_rules(wallet_rules_path).model_copy(update={"verification_months_before_renewal": n})
    m = Member(member_id="SYN-0001", display_name="x", renewal_date=renewal)
    assert compute_deadlines(m, rules) == (months, due)
