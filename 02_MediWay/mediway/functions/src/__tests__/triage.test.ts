import { describe, it, expect, vi, beforeEach } from 'vitest';
import { HttpsError } from 'firebase-functions/v2/https';
import {
  callClaudeHaiku,
  performTriage,
  type TriageDeps,
  type TriageRecommendation,
} from '../triage';

const callLlmMock = vi.fn();
const checkRateMock = vi.fn();
const auditMock = vi.fn();

const deps: TriageDeps = {
  callLlm: (s) => callLlmMock(s),
  checkRateLimit: (u) => checkRateMock(u),
  audit: (u, r) => auditMock(u, r),
};

beforeEach(() => {
  callLlmMock.mockReset();
  checkRateMock.mockReset();
  auditMock.mockReset();
});

describe('performTriage', () => {
  it('증상 3자 미만 거부', async () => {
    await expect(performTriage('uid', 'ab', deps)).rejects.toBeInstanceOf(
      HttpsError,
    );
    expect(callLlmMock).not.toHaveBeenCalled();
  });

  it('증상 500자 초과 거부', async () => {
    await expect(
      performTriage('uid', 'a'.repeat(501), deps),
    ).rejects.toBeInstanceOf(HttpsError);
  });

  it('정상 — 상위 3개 slice + 유효성 필터 + audit 호출', async () => {
    checkRateMock.mockResolvedValueOnce(undefined);
    callLlmMock.mockResolvedValueOnce([
      { department: '내과', confidence: 0.9, reason: 'r1' },
      { department: '이비인후과', confidence: 0.7, reason: 'r2' },
      { department: '감염내과', confidence: 0.6, reason: 'r3' },
      { department: '신경과', confidence: 0.4, reason: 'r4' },
    ] satisfies TriageRecommendation[]);

    const r = await performTriage('uid-a', '기침과 고열 3일', deps);

    expect(r.recommendations).toHaveLength(3);
    expect(r.recommendations[0].department).toBe('내과');
    expect(r.disclaimer).toContain('진단');
    expect(checkRateMock).toHaveBeenCalledWith('uid-a');
    expect(auditMock).toHaveBeenCalledWith('uid-a', [
      '내과',
      '이비인후과',
      '감염내과',
    ]);
  });

  it('유효하지 않은 항목 필터링 → 0개면 internal 에러', async () => {
    checkRateMock.mockResolvedValueOnce(undefined);
    callLlmMock.mockResolvedValueOnce([
      { department: '', confidence: 0.9, reason: 'r' }, // 빈 dept 제외
      { department: '이비인후과', confidence: '0.7', reason: 'r' }, // wrong type
    ] as unknown as TriageRecommendation[]);

    await expect(
      performTriage('uid-a', '기침 3일', deps),
    ).rejects.toBeInstanceOf(HttpsError);
    expect(auditMock).not.toHaveBeenCalled();
  });

  it('rateLimit throw 시 bubble up', async () => {
    checkRateMock.mockRejectedValueOnce(
      new HttpsError('resource-exhausted', 'over limit'),
    );
    await expect(
      performTriage('uid', '기침 3일', deps),
    ).rejects.toMatchObject({ code: 'resource-exhausted' });
    expect(callLlmMock).not.toHaveBeenCalled();
  });

  it('trimmed 공백 ≥3자 OK', async () => {
    checkRateMock.mockResolvedValueOnce(undefined);
    callLlmMock.mockResolvedValueOnce([
      { department: '내과', confidence: 0.8, reason: 'r' },
    ]);
    const r = await performTriage('uid', '   기침 2일   ', deps);
    expect(r.recommendations[0].department).toBe('내과');
  });
});

// callClaudeHaiku — axios mock
vi.mock('axios', () => ({
  default: {
    post: vi.fn(),
  },
}));
import axios from 'axios';
const axiosPost = axios.post as unknown as ReturnType<typeof vi.fn>;

describe('callClaudeHaiku', () => {
  beforeEach(() => {
    axiosPost.mockReset();
  });

  it('정상 JSON 응답 파싱', async () => {
    axiosPost.mockResolvedValueOnce({
      data: {
        content: [
          {
            text: '{"recommendations":[{"department":"내과","confidence":0.9,"reason":"r"}]}',
          },
        ],
      },
    });
    const r = await callClaudeHaiku('기침 고열', 'sk-test');
    expect(r).toHaveLength(1);
    expect(r[0].department).toBe('내과');

    const [url, body, config] = axiosPost.mock.calls[0];
    expect(url).toContain('api.anthropic.com');
    expect(body.model).toMatch(/haiku/);
    expect(config.headers['x-api-key']).toBe('sk-test');
  });

  it('JSON 없으면 빈 배열', async () => {
    axiosPost.mockResolvedValueOnce({
      data: { content: [{ text: 'not json at all' }] },
    });
    const r = await callClaudeHaiku('증상', 'sk');
    expect(r).toEqual([]);
  });

  it('래핑 텍스트 속 JSON 블록도 추출', async () => {
    axiosPost.mockResolvedValueOnce({
      data: {
        content: [
          {
            text: '설명문입니다. {"recommendations":[{"department":"외과","confidence":0.5,"reason":"x"}]} 추가 설명',
          },
        ],
      },
    });
    const r = await callClaudeHaiku('증상', 'sk');
    expect(r[0].department).toBe('외과');
  });
});
