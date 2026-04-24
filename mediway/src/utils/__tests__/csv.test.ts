import { describe, it, expect } from 'vitest';
import { toCsv } from '../csv';

describe('toCsv', () => {
  it('기본 헤더와 행을 생성한다', () => {
    const rows = [
      { name: 'Alice', age: 30 },
      { name: 'Bob', age: 25 },
    ];
    const out = toCsv(rows, [
      { key: 'name', label: '이름' },
      { key: 'age', label: '나이' },
    ]);
    expect(out).toBe('이름,나이\nAlice,30\nBob,25');
  });

  it('쉼표·따옴표·개행을 이스케이프한다', () => {
    const rows = [{ note: 'a, b' }, { note: 'c "quote"' }, { note: 'line\nbreak' }];
    const out = toCsv(rows, [{ key: 'note', label: 'note' }]);
    expect(out).toBe('note\n"a, b"\n"c ""quote"""\n"line\nbreak"');
  });

  it('null/undefined은 빈 문자열로 처리한다', () => {
    const rows = [{ v: null }, { v: undefined }];
    const out = toCsv(rows, [{ key: 'v', label: 'v' }]);
    expect(out).toBe('v\n\n');
  });
});
