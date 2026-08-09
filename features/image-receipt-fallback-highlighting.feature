# mutation-stamp: sha256=99172becbfd53f9906c6d60abd209856bb58e5c44da2f27cdb0e1fa3924c3570
# acceptance-mutation-manifest-begin
# {"version":1,"tested_at":"2026-08-09T02:38:16.540819792Z","feature_name":"Image receipt fallback highlighting","feature_path":"features/image-receipt-fallback-highlighting.feature","background_hash":"655932d41cb1b98ae2a94f3952fe7f0e5c200e984fe7cde90ece646db6de47fc","implementation_hash":"sha256:ccb5294d9e1c6a8ac018c4a87b005452620c81d29a939a893f228c7ec93c8e6f","scenarios":[{"index":0,"name":"Image receipt fallback highlighting 001","scenario_hash":"8f18ab44331fbb36aaf3f0eb8b60d0e4de9f45d6e8b56cff5991c98813c32ba1","mutation_count":4,"result":{"Total":4,"Killed":4,"Survived":0,"Errors":0},"tested_at":"2026-08-09T02:37:53.702078746Z"},{"index":1,"name":"Image receipt fallback highlighting 002","scenario_hash":"5c4b5f5aa4c7970e07c39aa209ca7f3df3dd47bcd359ee8c6f45568fd0d85b2b","mutation_count":8,"result":{"Total":8,"Killed":8,"Survived":0,"Errors":0},"tested_at":"2026-08-09T02:37:53.702078746Z"},{"index":2,"name":"Image receipt fallback highlighting 003","scenario_hash":"fcf6ea1e130c6e0e99875807bb2438288d36e6c3ba40bf0de22b6d5adefa618e","mutation_count":8,"result":{"Total":8,"Killed":8,"Survived":0,"Errors":0},"tested_at":"2026-08-09T02:37:53.702078746Z"}]}
# acceptance-mutation-manifest-end

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
