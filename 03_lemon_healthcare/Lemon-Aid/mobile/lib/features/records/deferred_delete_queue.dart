// features/records/deferred_delete_queue.dart — 실행취소용 지연 삭제 큐
//
// 가이드 07 ④/⑨ + 백엔드 공백 3(restore 라우트 없음): 삭제는 낙관적으로 화면에서
// 즉시 제거하되, 실제 백엔드 commit 은 4초 지연한다. 그 사이 '실행취소' 를 누르면
// 타이머를 취소하고 commit 을 보내지 않는다(클라이언트 측 undo). 화면 dispose 시
// 보류 중인 삭제는 [flush] 로 즉시 commit 해 유실을 막는다.
//
// 연산·영속은 모두 백엔드. 여기서는 타이밍과 취소만 관리한다.

import 'dart:async';

/// 실행취소를 위한 지연 삭제 commit 큐.
class DeferredDeleteQueue {
  /// 지연 시간(기본 4초)을 받아 큐를 만든다.
  DeferredDeleteQueue({this.delay = const Duration(seconds: 4)});

  /// commit 까지의 지연 시간.
  final Duration delay;

  final Map<String, _PendingDelete> _pending = <String, _PendingDelete>{};

  /// 현재 보류 중인 삭제가 있는지.
  bool get hasPending => _pending.isNotEmpty;

  /// [id] 가 보류 중인지.
  bool isPending(String id) => _pending.containsKey(id);

  /// [id] 삭제를 예약한다. [delay] 후 [commit] 을 1회 호출한다.
  ///
  /// 같은 [id] 가 이미 보류 중이면 기존 타이머를 취소하고 새로 예약한다.
  void schedule(String id, Future<void> Function() commit) {
    _pending.remove(id)?.timer.cancel();
    final Timer timer = Timer(delay, () {
      final _PendingDelete? entry = _pending.remove(id);
      if (entry == null) return;
      // commit 실패는 호출자(onError)에게 위임. 미지정이면 조용히 무시한다
      // (낙관적 제거는 이미 끝났고, soft-delete 재시도는 다음 액션에서 가능).
      unawaited(_runCommit(entry));
    });
    _pending[id] = _PendingDelete(commit: commit, timer: timer);
  }

  /// [id] 의 보류 삭제를 취소한다 (실행취소). 취소되면 true.
  bool undo(String id) {
    final _PendingDelete? entry = _pending.remove(id);
    if (entry == null) return false;
    entry.timer.cancel();
    return true;
  }

  /// 보류 중인 모든 삭제를 즉시 commit 한다 (dispose 시 유실 방지).
  Future<void> flush() async {
    final List<_PendingDelete> entries = _pending.values.toList(
      growable: false,
    );
    _pending.clear();
    for (final _PendingDelete entry in entries) {
      entry.timer.cancel();
      await _runCommit(entry);
    }
  }

  /// 보류 중인 삭제를 모두 버린다 (commit 하지 않음).
  void dispose() {
    for (final _PendingDelete entry in _pending.values) {
      entry.timer.cancel();
    }
    _pending.clear();
  }

  Future<void> _runCommit(_PendingDelete entry) async {
    try {
      await entry.commit();
    } catch (_) {
      // 지연 commit 실패는 화면 상태를 되돌리지 않는다(낙관적 제거 유지).
      // 호출자는 schedule 의 commit 클로저 안에서 직접 에러를 처리할 수 있다.
    }
  }
}

class _PendingDelete {
  _PendingDelete({required this.commit, required this.timer});

  final Future<void> Function() commit;
  final Timer timer;
}
