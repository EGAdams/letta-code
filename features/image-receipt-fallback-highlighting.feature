# Image receipt fallback highlighting 001
# Image receipt fallback highlighting 002
# Image receipt fallback highlighting 003
Feature: Image receipt fallback highlighting

  Background:
    Given the dashboard is open to a Verified Transactions report

  Scenario Outline: Image receipt fallback highlighting 001
    Given expense <expense> has an available local image receipt
    And the established receipt matcher finds no eligible region
    And fallback matching confidently identifies the single payment region containing <target_region>
    When the user opens Set Category for expense <expense>
    And the user selects View Receipt
    Then the receipt viewer opens an annotated copy
    And exactly one red box encloses <target_region>
    And no unrelated receipt region is enclosed

    Examples:
      | expense | target_region                                          |
      | 2004    | the 125.00 check face payable to John Roark             |
      | 2006    | the 30.00 check face payable to Gabrielle McKay         |

  Scenario Outline: Image receipt fallback highlighting 002
    Given image receipt fixture <expense> is available
    And the established receipt matcher finds no eligible region
    And the fallback outcome is <fallback_result>
    When the user opens Set Category for expense <expense>
    And the user selects View Receipt
    Then the original receipt opens without a red box
    And no receipt region is presented as the matching expense

    Examples:
      | expense                | fallback_result                 |
      | unmatched-check        | no confident region             |
      | ambiguous-checks       | two indistinguishable regions   |
      | invalid-bounds-check   | a region outside the receipt    |
      | offline-fallback-check | an unavailable matching service |

  Scenario Outline: Image receipt fallback highlighting 003
    Given expense <expense> has an available local image supporting document
    And the established receipt matcher identifies <target_region>
    And the supporting document also contains <confusing_region>
    When the user opens Set Category for expense <expense>
    And the user selects <viewer_action>
    Then exactly one red box encloses <target_region>
    And no red box encloses <confusing_region>

    Examples:
      | expense | viewer_action          | target_region                                 | confusing_region                     |
      | 1985    | View Receipt           | the DTE charge line for 53.06                 | the repeated total and dated balance |
      | 1522    | View Scanned Statement | the APPLE.COM row including its amount column | the adjacent statement rows          |
