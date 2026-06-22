import 'package:flutter_test/flutter_test.dart';
import 'package:lemon_aid_mobile/features/supplements/supplement_models.dart';

void main() {
  test('parses supplement preview and serializes registration payload', () {
    final SupplementAnalysisPreview preview =
        SupplementAnalysisPreview.fromJson(<String, dynamic>{
          'analysis_id': '00000000-0000-0000-0000-000000000001',
          'status': 'requires_confirmation',
          'parsed_product': <String, dynamic>{
            'product_name': 'Vitamin D',
            'manufacturer': 'Lemon Labs',
            'serving_size': '1 capsule',
            'daily_servings': 1,
          },
          'ingredient_candidates': <Map<String, dynamic>>[
            <String, dynamic>{
              'display_name': '비타민 D',
              'original_name': 'Vitamin D',
              'nutrient_code': 'vitamin_d',
              'amount': 25,
              'unit': 'ug',
              'confidence': 0.8,
              'source': 'ocr_llm_preview',
            },
          ],
          'layout_available': true,
          'label_sections': <Map<String, dynamic>>[
            <String, dynamic>{
              'section_id': 'section-001',
              'section_type': 'ingredients',
              'heading_text': 'Supplement Facts',
              'text_bundle': 'Vitamin D 25 ug',
              'confidence': 0.8,
              'requires_review': false,
              'evidence_refs': <String>['span-001'],
            },
          ],
          'intake_method': <String, dynamic>{
            'text': 'Take 1 capsule daily.',
            'structured': <String, dynamic>{
              'frequency': 'daily',
              'times_per_day': 1,
              'amount_per_time': 1,
              'amount_unit': 'capsule',
              'time_of_day': <String>['morning'],
              'with_food': 'unknown',
            },
            'confidence': 0.82,
            'requires_review': false,
            'evidence_refs': <String>['span-002'],
          },
          'precautions': <Map<String, dynamic>>[
            <String, dynamic>{
              'text': 'Consult a professional if pregnant.',
              'category': 'pregnancy',
              'severity': 'label_caution',
              'confidence': 0.9,
              'requires_review': false,
              'evidence_refs': <String>['span-003'],
            },
          ],
          'functional_claims': <Map<String, dynamic>>[
            <String, dynamic>{
              'text': 'Supports normal bone health.',
              'claim_type': 'label_claim',
              'confidence': 0.85,
              'requires_review': false,
              'evidence_refs': <String>['span-004'],
            },
          ],
          'evidence_spans': <Map<String, dynamic>>[
            <String, dynamic>{
              'span_id': 'span-001',
              'source_type': 'label_layout',
              'section_type': 'ingredients',
              'text_excerpt': 'Vitamin D 25 ug',
              'page_index': 0,
              'cell_ref': 'section-001:r0:c0',
              'confidence': 0.8,
            },
          ],
          'image_quality_report': <String, dynamic>{
            'status': 'retake_recommended',
            'issues': <Map<String, dynamic>>[
              <String, dynamic>{
                'reason_code': 'cover_only',
                'severity': 'retake',
                'message': 'Only the front label is visible.',
                'evidence': <String, dynamic>{'label': 'brand_front_label'},
              },
            ],
            'metrics': <String, dynamic>{
              'image_width': 400,
              'image_height': 300,
            },
            'detected_rois': <Map<String, dynamic>>[
              <String, dynamic>{
                'label': 'brand_front_label',
                'x': 10,
                'y': 20,
                'width': 180,
                'height': 220,
                'confidence': 0.94,
                'area_ratio': 0.33,
              },
            ],
            'retake_reasons': <String>['cover_only'],
          },
          'analysis_scope': 'identity_only',
          'action_required': 'additional_label_image_required',
          'detected_product_regions': <Map<String, dynamic>>[
            <String, dynamic>{
              'region_id': 'roi-001',
              'label': 'brand_front_label',
              'x': 10,
              'y': 20,
              'width': 180,
              'height': 220,
              'confidence': 0.94,
              'area_ratio': 0.33,
              'selected': true,
            },
          ],
          'selected_region_id': 'roi-001',
          'missing_required_sections': <String>['supplement_facts'],
          'image_role': 'front_label',
          'multi_image_group_id': null,
          'source_type': 'uploaded_image',
          'identity_conflict': <String, dynamic>{
            'conflict_type': 'barcode_product_mismatch',
            'severity': 'review',
            'message': 'Confirm product identity.',
            'evidence': <String, dynamic>{
              'barcode_candidate_count': 1,
              'parsed_product_present': true,
            },
          },
          'pipeline_metadata': <String, dynamic>{
            'intake_completed': true,
            'image_count': 1,
            'image_role': 'supplement_facts',
            'vision_roi_used': true,
            'ocr_status': 'success',
            'vision_status': 'success',
            'llm_status': 'warning',
            'ocr_provider': 'paddleocr_local',
            'ocr_text_present': true,
            'ocr_confidence_bucket': 'high',
            'roi_count': 1,
            'section_count': 1,
            'llm_parser_used': true,
            'parser_contract_version': 'test-parser-v3',
            'missing_required_sections': <String>['intake_method'],
            'raw_image_stored': false,
            'raw_ocr_text_stored': false,
          },
          'matched_product_candidates': <Object>[],
          'low_confidence_fields': <String>['manufacturer'],
          'warnings': <String>['User confirmation required.'],
          'algorithm_version': 'test',
          'source_manifest_version': null,
          'expires_at': '2026-05-15T00:00:00Z',
        });

    expect(preview.parsedProduct.productName, 'Vitamin D');
    expect(preview.ingredientCandidates.single.displayName, '비타민 D');
    expect(preview.ingredientCandidates.single.originalName, 'Vitamin D');
    expect(preview.ingredientCandidates.single.amount, 25);
    expect(preview.layoutAvailable, isTrue);
    expect(preview.labelSections.single.textBundle, 'Vitamin D 25 ug');
    expect(preview.intakeMethod.structured.timesPerDay, 1);
    expect(preview.precautions.single.category, 'pregnancy');
    expect(preview.functionalClaims.single.claimType, 'label_claim');
    expect(preview.evidenceSpans.single.textExcerpt, 'Vitamin D 25 ug');
    expect(preview.imageQualityReport?.issues.single.reasonCode, 'cover_only');
    expect(preview.actionRequired, 'additional_label_image_required');
    expect(preview.blocksRegistrationForImageRisk, isTrue);
    expect(preview.detectedProductRegions.single.regionId, 'roi-001');
    expect(preview.missingRequiredSections.single, 'supplement_facts');
    expect(preview.identityConflict?.conflictType, 'barcode_product_mismatch');
    expect(preview.pipelineMetadata.ocrProvider, 'paddleocr_local');
    expect(preview.pipelineMetadata.ocrStatus, 'success');
    expect(preview.pipelineMetadata.visionStatus, 'success');
    expect(preview.pipelineMetadata.llmStatus, 'warning');
    expect(preview.pipelineMetadata.imageCount, 1);
    expect(preview.pipelineMetadata.imageRole, 'supplement_facts');
    expect(preview.pipelineMetadata.ocrTextPresent, isTrue);
    expect(preview.pipelineMetadata.ocrConfidenceBucket, 'high');
    expect(preview.pipelineMetadata.roiCount, 1);
    expect(preview.pipelineMetadata.sectionCount, 1);
    expect(preview.pipelineMetadata.visionRoiUsed, isTrue);
    expect(preview.pipelineMetadata.llmParserUsed, isTrue);
    expect(preview.pipelineMetadata.parserContractVersion, 'test-parser-v3');
    expect(preview.pipelineMetadata.missingRequiredSections, <String>[
      'intake_method',
    ]);
    expect(preview.pipelineMetadata.rawOcrTextStored, isFalse);

    final UserSupplementCreate request = UserSupplementCreate(
      analysisId: preview.analysisId,
      displayName: 'Vitamin D',
      manufacturer: 'Lemon Labs',
      ingredients: const <UserSupplementIngredientInput>[
        UserSupplementIngredientInput(
          displayName: 'Vitamin D',
          originalName: 'Vitamin D',
          nutrientCode: 'vitamin_d',
          amount: 25,
          unit: 'ug',
          confidence: 0.8,
          source: 'ocr_llm_preview',
        ),
      ],
      serving: const SupplementServing(
        amount: 1,
        unit: 'capsule',
        dailyServings: 1,
      ),
      intakeSchedule: const SupplementIntakeSchedule(
        frequency: 'daily',
        timeOfDay: <String>['morning'],
      ),
      precautionSnapshot: const <String>['임신 중이면 전문가와 상담하세요.'],
      evidenceRefs: const <String>['span-001', 'span-002'],
    );

    expect(request.toJson()['user_confirmed'], true);
    expect(request.toJson()['analysis_id'], preview.analysisId);
    final List<dynamic> serializedIngredients =
        request.toJson()['ingredients'] as List<dynamic>;
    expect(serializedIngredients.single['original_name'], 'Vitamin D');
    expect(request.toJson()['precaution_snapshot'], <String>[
      '임신 중이면 전문가와 상담하세요.',
    ]);
    expect(request.toJson()['evidence_refs'], <String>['span-001', 'span-002']);
  });

  test('parses raw OCR text from the top-level field when present', () {
    final SupplementAnalysisPreview preview =
        SupplementAnalysisPreview.fromJson(<String, dynamic>{
          'analysis_id': '00000000-0000-0000-0000-000000000009',
          'status': 'requires_confirmation',
          'parsed_product': <String, dynamic>{},
          'ingredient_candidates': <Map<String, dynamic>>[],
          'algorithm_version': 'test',
          'expires_at': '2026-05-15T00:00:00Z',
          'raw_ocr_text': '비타민 D 1000\n비타민 D 25ug',
        });

    expect(preview.rawOcrText, '비타민 D 1000\n비타민 D 25ug');
  });

  test('leaves raw OCR text null when the field is absent', () {
    final SupplementAnalysisPreview preview =
        SupplementAnalysisPreview.fromJson(<String, dynamic>{
          'analysis_id': '00000000-0000-0000-0000-000000000009',
          'status': 'requires_confirmation',
          'parsed_product': <String, dynamic>{},
          'ingredient_candidates': <Map<String, dynamic>>[],
          'algorithm_version': 'test',
          'expires_at': '2026-05-15T00:00:00Z',
        });

    expect(preview.rawOcrText, isNull);
  });

  test('parses supplement analysis session response', () {
    final SupplementAnalysisSession session =
        SupplementAnalysisSession.fromJson(<String, dynamic>{
          'analysis_group_id': 'multi-001',
          'status': 'created',
          'image_count': 0,
          'max_images': 6,
          'missing_required_sections': <String>[
            'product_name',
            'supplement_facts',
            'intake_method',
            'precautions',
          ],
          'action_required': 'additional_label_image_required',
        });

    expect(session.analysisGroupId, 'multi-001');
    expect(session.status, 'created');
    expect(session.imageCount, 0);
    expect(session.maxImages, 6);
    expect(session.missingRequiredSections, <String>[
      'product_name',
      'supplement_facts',
      'intake_method',
      'precautions',
    ]);
  });

  test('parses multi-image supplement preview response', () {
    final SupplementMultiImageAnalysisPreview response =
        SupplementMultiImageAnalysisPreview.fromJson(<String, dynamic>{
          'analysis_group_id': 'multi-001',
          'image_count': 2,
          'previews': <Map<String, dynamic>>[
            _minimalPreview(
              analysisId: '00000000-0000-0000-0000-000000000001',
              imageRole: 'front_label',
            ),
            _minimalPreview(
              analysisId: '00000000-0000-0000-0000-000000000002',
              imageRole: 'supplement_facts',
              hasIngredient: true,
            ),
          ],
          'merged_preview': _minimalPreview(
            analysisId: '00000000-0000-0000-0000-000000000002',
            imageRole: 'mixed',
            hasIngredient: true,
          ),
          'missing_required_sections': <String>['intake_method'],
          'action_required': 'additional_label_image_required',
          'pipeline_metadata': <String, dynamic>{
            'intake_completed': true,
            'image_count': 2,
            'image_role': 'mixed',
            'vision_roi_used': false,
            'ocr_provider': 'intake-only',
            'llm_parser_used': false,
            'missing_required_sections': <String>['intake_method'],
            'raw_image_stored': false,
            'raw_ocr_text_stored': false,
          },
          'expires_at': '2026-05-15T00:00:00Z',
        });

    expect(response.analysisGroupId, 'multi-001');
    expect(response.imageCount, 2);
    expect(response.previews.last.imageRole, 'supplement_facts');
    expect(response.mergedPreview?.imageRole, 'mixed');
    expect(response.pipelineMetadata.imageCount, 2);
    expect(response.pipelineMetadata.imageRole, 'mixed');
    expect(response.missingRequiredSections, <String>['intake_method']);
    expect(
      response.primaryPreview?.analysisId,
      '00000000-0000-0000-0000-000000000002',
    );
    expect(response.primaryPreview?.imageRole, 'mixed');
    // result_mode defaults to single_product when absent (backward compatible).
    expect(response.resultMode, 'single_product');
    expect(response.isDistinctProducts, false);
  });

  test('parses distinct_products multi-image preview as separate products', () {
    final SupplementMultiImageAnalysisPreview response =
        SupplementMultiImageAnalysisPreview.fromJson(<String, dynamic>{
          'analysis_group_id': 'multi-distinct-001',
          'image_count': 2,
          'previews': <Map<String, dynamic>>[
            _minimalPreview(
              analysisId: '00000000-0000-0000-0000-0000000000a1',
              imageRole: 'front_label',
              hasIngredient: true,
            ),
            _minimalPreview(
              analysisId: '00000000-0000-0000-0000-0000000000a2',
              imageRole: 'front_label',
              hasIngredient: true,
            ),
          ],
          'missing_required_sections': <String>[],
          'action_required': 'review_required',
          'pipeline_metadata': <String, dynamic>{
            'intake_completed': true,
            'image_count': 2,
            'raw_image_stored': false,
            'raw_ocr_text_stored': false,
          },
          'expires_at': '2026-05-15T00:00:00Z',
          'result_mode': 'distinct_products',
        });

    expect(response.resultMode, 'distinct_products');
    expect(response.isDistinctProducts, true);
    expect(response.mergedPreview, isNull);
    expect(response.previews.length, 2);
    // With no merged preview, primaryPreview still resolves (first reviewable).
    expect(response.primaryPreview, isNotNull);
  });

  test('parses supplement impact preview response', () {
    final SupplementImpactPreviewResponse response =
        SupplementImpactPreviewResponse.fromJson(<String, dynamic>{
          'calculation_version': 'supplement-impact-v1.0.0',
          'reference_version': '2025',
          'source_manifest_version': null,
          'data_status': 'partial',
          'current_supplement_contributions': <Map<String, dynamic>>[
            <String, dynamic>{
              'nutrient_code': 'vitamin_d_ug',
              'nutrient_name': 'Vitamin D',
              'reference_unit': 'ug',
              'total_daily_amount': 25,
              'original_unit_totals': <String, dynamic>{'ug': 25},
              'contribution_count': 1,
              'supplement_ids': <String>[],
              'items': <Object>[],
              'warnings': <String>[],
            },
          ],
          'deficiency_support_candidates': <Map<String, dynamic>>[],
          'excess_or_duplicate_risks': <Map<String, dynamic>>[
            <String, dynamic>{
              'nutrient_code': 'vitamin_d_ug',
              'nutrient_name': 'Vitamin D',
              'action_label': 'avoid_duplicate',
              'reason_code': 'duplicate_supplement_source',
              'current_food_or_recorded_amount': null,
              'supplement_daily_amount': 25,
              'estimated_total_amount': null,
              'reference_amount': null,
              'reference_unit': 'ug',
              'ul_amount': null,
              'contributing_supplements': <String>[],
              'evidence': <Object>[],
              'user_message': 'Check duplicate supplement sources.',
            },
          ],
          'missing_profile_fields': <String>['age'],
          'safe_user_message': 'Review current supplement intake.',
          'clinical_disclaimer': 'Reference information only.',
          'warnings': <String>['partial_profile'],
          'requires_user_confirmation': true,
        });

    expect(response.dataStatus, 'partial');
    expect(response.currentSupplementContributions.single.totalDailyAmount, 25);
    expect(
      response.excessOrDuplicateRisks.single.actionLabel,
      'avoid_duplicate',
    );
    expect(
      response.toJson()['calculation_version'],
      'supplement-impact-v1.0.0',
    );
  });
}

Map<String, dynamic> _minimalPreview({
  required String analysisId,
  required String imageRole,
  bool hasIngredient = false,
}) {
  return <String, dynamic>{
    'analysis_id': analysisId,
    'status': 'requires_confirmation',
    'parsed_product': <String, dynamic>{},
    'ingredient_candidates': hasIngredient
        ? <Map<String, dynamic>>[
            <String, dynamic>{
              'display_name': 'Vitamin D',
              'nutrient_code': 'vitamin_d',
              'amount': 25,
              'unit': 'ug',
              'confidence': 0.8,
              'source': 'ocr_llm_preview',
            },
          ]
        : <Map<String, dynamic>>[],
    'matched_product_candidates': <Object>[],
    'image_role': imageRole,
    'pipeline_metadata': <String, dynamic>{
      'intake_completed': true,
      'image_count': 1,
      'image_role': imageRole,
      'vision_roi_used': false,
      'ocr_provider': 'intake-only',
      'llm_parser_used': false,
      'raw_image_stored': false,
      'raw_ocr_text_stored': false,
    },
    'low_confidence_fields': <String>[],
    'warnings': <String>[],
    'algorithm_version': 'test',
    'source_manifest_version': null,
    'expires_at': '2026-05-15T00:00:00Z',
  };
}
