// features/records/records_providers.dart — 캘린더 기록 Provider
//
// RecordsRepository 를 앱 백엔드 리포지토리 위에 올린다. 캘린더 화면 전용으로
// 홈 컨트롤러와 분리한다.

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../app_providers.dart';
import 'records_repository.dart';

/// 캘린더 월 단위 기록 리포지토리 Provider.
final Provider<RecordsRepository> recordsRepositoryProvider =
    Provider<RecordsRepository>((Ref ref) {
      return RecordsRepository(
        repository: ref.watch(lemonAidRepositoryProvider),
      );
    });
