# Image receipt fallback strategy 001
# Image receipt fallback strategy 002
# Image receipt fallback strategy 003
Feature: Image receipt fallback strategy

  Background:
    Given document annotation supports image, PDF, and Excel supporting documents

  Scenario Outline: Image receipt fallback strategy 001
    Given established image matching returns <established_result>
    When image annotation is requested
    Then fallback matching is requested <fallback_calls> times

    Examples:
      | established_result  | fallback_calls |
      | an eligible region  | 0              |
      | no region           | 1              |

  Scenario Outline: Image receipt fallback strategy 002
    Given established image matching uses decisive score <decisive_score>
    And its line-scoring and physical-row tie rules are unchanged
    When fallback matching is added
    Then decisive score remains <decisive_score>
    And the established line-scoring and physical-row tie results remain unchanged

    Examples:
      | decisive_score |
      | 10             |

  Scenario Outline: Image receipt fallback strategy 003
    Given <document_format> annotation is selected through the expense document annotator contract
    When fallback matching is added
    Then the expense document annotator contract remains unchanged
    And <document_format> annotation remains selectable through that contract

    Examples:
      | document_format |
      | image           |
      | PDF             |
      | Excel           |
