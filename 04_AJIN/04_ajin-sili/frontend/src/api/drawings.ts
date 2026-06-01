// P2 — 도면 메타 검색 + Vision 캡션 인덱스 API 클라이언트
// 백엔드 backend/routers/search.py 의 /search/drawings 시리즈와 1:1 정합.

import { api } from './client';

export interface DrawingItem {
  id: number;
  drawing_number: string;
  part_number: string;
  part_name: string;
  revision: string;
  equipment_type: string;
  material: string;
  process_type: string;
  department: string;
  file_path: string;
  description: string;
  bom_info: string;
  source_type: 'drawing';
}

export interface DrawingListResponse {
  items: DrawingItem[];
  total: number;
}

export interface DrawingCaptionItem {
  id: number;
  caption: string;
  keywords: string;
  department: string;
  uploader: string;
  file_name: string;
  image_size: number;
  source_model: string;
  created_at: string;
  source_type: 'caption';
}

export interface DrawingCaptionListResponse {
  items: DrawingCaptionItem[];
  total: number;
}

export interface AddCaptionRequest {
  caption: string;
  keywords?: string;
  department?: string;
  uploader?: string;
  file_name?: string;
  image_size?: number;
  source_model?: string;
}

export interface AddCaptionResponse {
  id: number;
  total: number;
}

export async function searchDrawings(
  q = '',
  equipment_type = '',
  department = '',
): Promise<DrawingListResponse> {
  const { data } = await api.get<DrawingListResponse>('/search/drawings', {
    params: { q, equipment_type, department },
  });
  return data;
}

export async function searchDrawingCaptions(
  q = '',
  department = '',
  limit = 20,
): Promise<DrawingCaptionListResponse> {
  const { data } = await api.get<DrawingCaptionListResponse>(
    '/search/drawings/captions',
    { params: { q, department, limit } },
  );
  return data;
}

export async function addDrawingCaption(req: AddCaptionRequest): Promise<AddCaptionResponse> {
  const { data } = await api.post<AddCaptionResponse>('/search/drawings/captions', req);
  return data;
}

export async function getDrawingDetail(id: number): Promise<DrawingItem> {
  const { data } = await api.get<DrawingItem>(`/search/drawings/${id}`);
  return data;
}

// 결과 카드에서 단축 thumbnail 경로 — 실제 파일은 v2.0 에서 연동. PoC 는 자산 종류별 placeholder.
export function drawingThumbnail(equipment_type?: string): string {
  // /public/drawings/thumbnails/{type}.svg — 미존재 시 generic.svg fallback
  const t = (equipment_type || '').trim().toLowerCase() || 'generic';
  return `/drawings/thumbnails/${encodeURIComponent(t)}.svg`;
}
