# mutation-stamp: sha256=22efef3d9d2f3e8f71d3dce5a3167d62a53d7d9f01839ad4ab27aa24a41c6459
# acceptance-mutation-manifest-begin
# {"version":1,"tested_at":"2026-08-09T02:38:16.106912467Z","feature_name":"Image receipt fallback strategy","feature_path":"features/image-receipt-fallback-strategy.feature","background_hash":"ddeedff506d69df60137db8845f727938f8d9d1cd59466d72e04b2e15c0a5b46","implementation_hash":"sha256:6b4794b7a294f3d39d6d2fc4eb7f27972a05482cc480ae4234426d54d2d06889","scenarios":[{"index":0,"name":"Image receipt fallback strategy 001","scenario_hash":"2443fd29ead566b6caa5c72ca5b92574c33fa8166e6ec8248e23853cda6fb895","mutation_count":4,"result":{"Total":4,"Killed":4,"Survived":0,"Errors":0},"tested_at":"2026-08-09T02:37:52.942280419Z"},{"index":1,"name":"Image receipt fallback strategy 002","scenario_hash":"44558fdc755e4a46361993c5646c5bb5b9669d3a6a5c5214ec2101fa0b90b412","mutation_count":1,"result":{"Total":1,"Killed":1,"Survived":0,"Errors":0},"tested_at":"2026-08-09T02:37:52.942280419Z"},{"index":2,"name":"Image receipt fallback strategy 003","scenario_hash":"41094aef2461c4bdaebcc6c121a0d446d410ee8e5bb0b20ea99d58af8034048f","mutation_count":3,"result":{"Total":3,"Killed":3,"Survived":0,"Errors":0},"tested_at":"2026-08-09T02:37:52.942280419Z"}]}
# acceptance-mutation-manifest-end

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
