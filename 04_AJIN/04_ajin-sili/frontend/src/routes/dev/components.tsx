// 컴포넌트 카탈로그 (DEV 모드 전용) — /dev/components

import { useState } from 'react';
import { Map, Cpu, Settings } from 'lucide-react';
import { Card } from '@components/ui/Card';
import { GlassPanel } from '@components/ui/GlassPanel';
import { PanelHeader } from '@components/ui/PanelHeader';
import { DottedSeparator } from '@components/ui/DottedSeparator';
import { Tabs } from '@components/ui/Tabs';
import { Stepper } from '@components/ui/Stepper';
import { Modal } from '@components/ui/Modal';
import { Drawer } from '@components/ui/Drawer';
import { Tooltip } from '@components/ui/Tooltip';
import { Skeleton } from '@components/ui/Skeleton';
import { Button } from '@components/ui/Button';
import { Badge } from '@components/ui/Badge';
import { ErrorAlert } from '@components/ui/ErrorAlert';
import { MetricCard } from '@components/ui/MetricCard';
import { MarkdownRenderer } from '@components/ui/MarkdownRenderer';
import { DataTable } from '@components/ui/DataTable';
import { TextField, SelectField } from '@components/form/FormField';
import { PlotlyChart } from '@components/chart/PlotlyChart';
import { MapView, type MapMarker } from '@components/chart/MapView';
import { useToast } from '@store/toast';

const SAMPLE_DATA = [
  { id: 'QA-0001', name: '김민수', position: '차장', dept: '품질보증팀' },
  { id: 'PE-0019', name: '최유진', position: '대리', dept: '생산기술팀' },
  { id: 'HR-0001', name: '이영희', position: '부장', dept: '인사팀' },
];

const SAMPLE_MARKERS: MapMarker[] = [
  { id: '1', lat: 35.871, lng: 128.601, name: '본사 (대구)', description: '본사 본사옥' },
  { id: '2', lat: 36.815, lng: 127.114, name: '천안 1공장' },
  { id: '3', lat: 35.180, lng: 129.075, name: '울산' },
  { id: '4', lat: 33.749, lng: -84.388, name: 'JOON INC (USA)' },
];

const PLOTLY_DATA = [
  {
    type: 'bar' as const,
    x: ['CCH', 'OBC', '범퍼빔', '도어', '볼시트'],
    y: [1.51, 1.18, 0.89, 1.62, 1.55],
    marker: { color: '#D89400' },
    name: 'Cpk',
  },
];

export function ComponentCatalog() {
  const { addToast } = useToast();
  const [tab, setTab] = useState('layout');
  const [modalOpen, setModalOpen] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);

  return (
    <div className="page" style={{ padding: 24 }}>
      <h1 className="h1">UI 컴포넌트 카탈로그</h1>
      <p className="dim">Day 3 산출물 — 16 컴포넌트 + 5 헬퍼 훅 (DEV 전용)</p>

      <Tabs
        items={[
          { id: 'layout', labelEn: 'LAYOUT', labelKo: '레이아웃' },
          { id: 'interaction', labelEn: 'INTERACTION', labelKo: '인터랙션' },
          { id: 'data', labelEn: 'DATA', labelKo: '데이터' },
          { id: 'chart', labelEn: 'CHART', labelKo: '차트·지도' },
        ]}
        active={tab}
        onChange={setTab}
      />

      {tab === 'layout' && (
        <div style={{ display: 'grid', gap: 24 }}>
          <section>
            <PanelHeader labelEn="CARD" labelKo="카드" />
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 }}>
              <Card><strong>Default</strong><p>기본 카드</p></Card>
              <Card variant="highlighted"><strong>Highlighted</strong><p>좌측 골드 띠</p></Card>
              <Card variant="flat" padding="sm"><strong>Flat / sm</strong></Card>
            </div>
          </section>

          <section>
            <PanelHeader labelEn="GLASS PANEL" labelKo="유리 패널" />
            <GlassPanel>
              <div style={{ padding: 16 }}>
                <strong>Liquid Glass</strong>
                <p>backdrop-filter blur 24px + saturate 140%</p>
              </div>
            </GlassPanel>
          </section>

          <section>
            <PanelHeader labelEn="METRIC CARDS" labelKo="메트릭 카드" />
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}>
              <MetricCard value={329} labelEn="EMPLOYEES" labelKo="사원" />
              <MetricCard value={201} labelEn="ERROR CODES" labelKo="에러코드" />
              <MetricCard value={29} labelEn="DEPARTMENTS" labelKo="부서" />
              <MetricCard value={33} labelEn="ACCOUNTS" labelKo="계정" />
            </div>
          </section>

          <DottedSeparator text="구분선" />

          <section>
            <PanelHeader labelEn="BADGES" labelKo="상태 배지" />
            <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
              <Badge status="ok">정상</Badge>
              <Badge status="warn">경고</Badge>
              <Badge status="fail">실패</Badge>
              <Badge status="info">정보</Badge>
              <Badge status="off">비활성</Badge>
              <Badge status="on">활성</Badge>
            </div>
          </section>
        </div>
      )}

      {tab === 'interaction' && (
        <div style={{ display: 'grid', gap: 24 }}>
          <section>
            <PanelHeader labelEn="BUTTONS" labelKo="버튼" />
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <Button variant="primary">Primary</Button>
              <Button variant="secondary">Secondary</Button>
              <Button variant="tertiary">Tertiary</Button>
              <Button variant="ghost">Ghost</Button>
              <Button variant="danger">Danger</Button>
              <Button loading>Loading</Button>
              <Button disabled>Disabled</Button>
              <Button icon={<Cpu size={14} />}>With Icon</Button>
            </div>
          </section>

          <section>
            <PanelHeader labelEn="STEPPER" labelKo="단계 표시" />
            <Stepper
              steps={[
                { id: 'a', title: '기본 정보', description: '사번 · 이름' },
                { id: 'b', title: '권한 설정', description: 'RBAC · 부서' },
                { id: 'c', title: '인증', description: '임시 비밀번호' },
              ]}
              current={1}
            />
          </section>

          <section>
            <PanelHeader labelEn="MODAL & DRAWER" labelKo="모달 · 드로워" />
            <div style={{ display: 'flex', gap: 8 }}>
              <Button onClick={() => setModalOpen(true)}>Modal 열기</Button>
              <Button onClick={() => setDrawerOpen(true)}>Drawer 열기</Button>
            </div>
            <Modal isOpen={modalOpen} onClose={() => setModalOpen(false)} title="시뮬레이션 결과">
              <p>이 모달은 ESC, 외부 클릭, X 버튼으로 닫을 수 있습니다.</p>
              <p>스크롤 가능한 본문이며 GlassPanel 매테리얼이 적용됩니다.</p>
            </Modal>
            <Drawer isOpen={drawerOpen} onClose={() => setDrawerOpen(false)} title="알람 상세" width={400}>
              <p>우측에서 슬라이드 인 (200ms ease-out)</p>
              <p>ESC로 닫기 + 외부 클릭 닫기</p>
            </Drawer>
          </section>

          <section>
            <PanelHeader labelEn="TOOLTIP" labelKo="툴팁" />
            <div style={{ display: 'flex', gap: 16 }}>
              <Tooltip content="상단 툴팁">
                <Button variant="ghost" icon={<Settings size={14} />}>Hover me</Button>
              </Tooltip>
              <Tooltip content="우측 툴팁" position="right">
                <Button variant="ghost">Right</Button>
              </Tooltip>
            </div>
          </section>

          <section>
            <PanelHeader labelEn="TOAST" labelKo="알림" />
            <div style={{ display: 'flex', gap: 8 }}>
              <Button onClick={() => addToast({ type: 'success', title: '저장 완료', message: '변경사항이 저장되었습니다.' })}>
                Success
              </Button>
              <Button onClick={() => addToast({ type: 'warning', message: 'Cpk 1.18 - 관리 한계 근접' })}>
                Warning
              </Button>
              <Button onClick={() => addToast({ type: 'error', title: '오류', message: '서버 응답 실패' })}>
                Error
              </Button>
              <Button onClick={() => addToast({ type: 'info', message: '새 알람 1건' })}>
                Info
              </Button>
            </div>
          </section>

          <section>
            <PanelHeader labelEn="ERROR ALERT" labelKo="에러 알림" />
            <ErrorAlert title="시스템 경고" message="Plotly 번들 로드 실패" severity="warning" />
            <ErrorAlert message="네트워크 연결을 확인해 주세요" severity="critical" />
          </section>

          <section>
            <PanelHeader labelEn="SKELETON" labelKo="스켈레톤 로딩" />
            <Skeleton variant="card" />
            <Skeleton variant="text" count={3} />
          </section>
        </div>
      )}

      {tab === 'data' && (
        <div style={{ display: 'grid', gap: 24 }}>
          <section>
            <PanelHeader labelEn="DATA TABLE" labelKo="데이터 테이블" />
            <DataTable
              data={SAMPLE_DATA}
              columns={[
                { accessorKey: 'id', header: '사번' },
                { accessorKey: 'name', header: '이름' },
                { accessorKey: 'position', header: '직급' },
                { accessorKey: 'dept', header: '부서' },
              ]}
              pageSize={5}
            />
          </section>

          <section>
            <PanelHeader labelEn="FORM FIELDS" labelKo="폼 필드" />
            <div style={{ maxWidth: 400 }}>
              <TextField name="empId" label="사원번호" required placeholder="QA-0001" />
              <TextField name="email" label="이메일" type="email" helperText="회사 이메일을 입력하세요" />
              <TextField name="pwd" label="비밀번호" type="password" error="8자 이상 입력하세요" />
              <SelectField
                name="dept"
                label="부서"
                options={[
                  { value: '', label: '선택' },
                  { value: 'qa', label: '품질보증팀' },
                  { value: 'pe', label: '생산기술팀' },
                ]}
              />
            </div>
          </section>

          <section>
            <PanelHeader labelEn="MARKDOWN" labelKo="마크다운 렌더링" />
            <Card>
              <MarkdownRenderer
                content={`## 8D Report — 부품 결함

**수신**: 현대자동차 SQ팀
**발신**: 아진산업 품질보증팀

---

### D1. 팀 구성
- 김민수 차장 (Lead)
- 이서연 대리

| 단계 | 책임자 | 완료 |
|---|---|---|
| D1 | 김민수 | ✓ |
| D2 | 이서연 | 진행 중 |

> 추가 정보는 [참고 문서](#)를 확인하세요.

\`\`\`
부품번호: ABC-1234
재질: SPCC
\`\`\``}
              />
            </Card>
          </section>
        </div>
      )}

      {tab === 'chart' && (
        <div style={{ display: 'grid', gap: 24 }}>
          <section>
            <PanelHeader labelEn="PLOTLY CHART" labelKo="Plotly 차트 (lazy)" />
            <Card padding="sm">
              <PlotlyChart
                data={PLOTLY_DATA}
                layout={{ title: { text: '5공정 Cpk 현황' } }}
                style={{ height: 300 }}
              />
            </Card>
            <p className="dim" style={{ fontSize: 12, marginTop: 8 }}>
              ● Network 탭에서 별도 chunk 로드 확인 (코드 스플리팅)
            </p>
          </section>

          <section>
            <PanelHeader labelEn="MAP VIEW" labelKo="사업장 지도 (OpenStreetMap)" />
            <MapView markers={SAMPLE_MARKERS} zoom={4} height={300} />
            <p className="dim" style={{ fontSize: 12, marginTop: 8 }}>
              <Map size={12} style={{ display: 'inline', verticalAlign: 'middle' }} />{' '}
              19개 사업장 — 다크/라이트 타일 자동 전환 (CartoDB)
            </p>
          </section>
        </div>
      )}
    </div>
  );
}
