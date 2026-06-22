import 'package:flutter_test/flutter_test.dart';
import 'package:lemon_aid_mobile/features/records/deferred_delete_queue.dart';

void main() {
  group('DeferredDeleteQueue', () {
    test('runs commit after the delay window', () async {
      // 짧은 지연으로 실제 타이머를 사용한다.
      final DeferredDeleteQueue queue = DeferredDeleteQueue(
        delay: const Duration(milliseconds: 20),
      );
      int committed = 0;
      queue.schedule('a', () async {
        committed += 1;
      });
      expect(queue.isPending('a'), isTrue);
      expect(committed, 0);
      await Future<void>.delayed(const Duration(milliseconds: 60));
      expect(committed, 1);
      expect(queue.isPending('a'), isFalse);
      expect(queue.hasPending, isFalse);
    });

    test('undo cancels a pending commit', () async {
      final DeferredDeleteQueue queue = DeferredDeleteQueue(
        delay: const Duration(milliseconds: 30),
      );
      int committed = 0;
      queue.schedule('a', () async {
        committed += 1;
      });
      final bool cancelled = queue.undo('a');
      expect(cancelled, isTrue);
      expect(queue.isPending('a'), isFalse);
      await Future<void>.delayed(const Duration(milliseconds: 60));
      expect(committed, 0);
    });

    test('undo on an unknown id returns false', () {
      final DeferredDeleteQueue queue = DeferredDeleteQueue();
      expect(queue.undo('missing'), isFalse);
    });

    test('flush commits all pending deletes immediately', () async {
      final DeferredDeleteQueue queue = DeferredDeleteQueue(
        delay: const Duration(seconds: 5),
      );
      final List<String> committed = <String>[];
      queue.schedule('a', () async => committed.add('a'));
      queue.schedule('b', () async => committed.add('b'));
      expect(queue.hasPending, isTrue);
      await queue.flush();
      expect(committed, containsAll(<String>['a', 'b']));
      expect(queue.hasPending, isFalse);
    });

    test('dispose drops pending deletes without committing', () async {
      final DeferredDeleteQueue queue = DeferredDeleteQueue(
        delay: const Duration(milliseconds: 20),
      );
      int committed = 0;
      queue.schedule('a', () async {
        committed += 1;
      });
      queue.dispose();
      await Future<void>.delayed(const Duration(milliseconds: 50));
      expect(committed, 0);
      expect(queue.hasPending, isFalse);
    });

    test('re-scheduling the same id resets the timer', () async {
      final DeferredDeleteQueue queue = DeferredDeleteQueue(
        delay: const Duration(milliseconds: 30),
      );
      int committed = 0;
      queue.schedule('a', () async => committed += 10);
      queue.schedule('a', () async => committed += 1);
      await Future<void>.delayed(const Duration(milliseconds: 60));
      // 두 번째 commit 만 실행된다.
      expect(committed, 1);
    });
  });
}
