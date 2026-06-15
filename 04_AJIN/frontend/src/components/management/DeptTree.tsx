// DeptTree.tsx — v4.8 F-Users. 좌측 부서 트리.
// 평면 DirectoryNode 리스트를 parent_id 기반으로 트리 재구성.
// 접기/펼치기 상태는 localStorage(`ajin-dept-tree-collapse`) 영속.
// 부서명 검색 input — 250ms debounce, 부분일치.

import { useEffect, useMemo, useRef, useState } from 'react';
import type { DirectoryNode } from '@api/management';

const COLLAPSE_KEY = 'ajin-dept-tree-collapse';

interface TreeNode extends DirectoryNode {
  children: TreeNode[];
}

function buildTree(nodes: DirectoryNode[]): TreeNode[] {
  const map = new Map<string, TreeNode>();
  for (const n of nodes) {
    map.set(n.id, { ...n, children: [] });
  }
  const roots: TreeNode[] = [];
  for (const n of nodes) {
    const t = map.get(n.id)!;
    if (n.parent_id && map.has(n.parent_id)) {
      map.get(n.parent_id)!.children.push(t);
    } else {
      roots.push(t);
    }
  }
  return roots;
}

function loadCollapse(): Set<string> {
  try {
    const raw = localStorage.getItem(COLLAPSE_KEY);
    if (!raw) return new Set();
    const arr = JSON.parse(raw);
    return Array.isArray(arr) ? new Set(arr) : new Set();
  } catch {
    return new Set();
  }
}

function saveCollapse(set: Set<string>): void {
  try {
    localStorage.setItem(COLLAPSE_KEY, JSON.stringify([...set]));
  } catch {
    // localStorage 차단 환경 무시.
  }
}

export interface DeptTreeProps {
  nodes: DirectoryNode[];
  totalUsers: number;
  selectedDept: string | null;
  onSelectDept: (department: string | null) => void;
}

export function DeptTree({ nodes, totalUsers, selectedDept, onSelectDept }: DeptTreeProps) {
  const [collapsed, setCollapsed] = useState<Set<string>>(() => loadCollapse());
  const [search, setSearch] = useState('');
  const [debounced, setDebounced] = useState('');
  const debounceRef = useRef<number | null>(null);

  useEffect(() => {
    if (debounceRef.current) window.clearTimeout(debounceRef.current);
    debounceRef.current = window.setTimeout(() => setDebounced(search.trim().toLowerCase()), 250);
    return () => {
      if (debounceRef.current) window.clearTimeout(debounceRef.current);
    };
  }, [search]);

  const tree = useMemo(() => buildTree(nodes), [nodes]);

  const matches = useMemo(() => {
    if (!debounced) return null;
    const out = new Set<string>();
    for (const n of nodes) {
      if (n.name.toLowerCase().includes(debounced)) {
        out.add(n.id);
        if (n.parent_id) out.add(n.parent_id);
      }
    }
    return out;
  }, [debounced, nodes]);

  const toggle = (id: string) => {
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      saveCollapse(next);
      return next;
    });
  };

  const renderNode = (node: TreeNode, depth: number) => {
    if (matches && !matches.has(node.id)) return null;
    const isCollapsed = collapsed.has(node.id);
    const hasChildren = node.children.length > 0;
    const isDept = node.level === 1;
    const isSelected = isDept && selectedDept === node.name;

    return (
      <div key={node.id}>
        <button
          type="button"
          className="lg-tree-row"
          onClick={() => {
            if (isDept) {
              onSelectDept(isSelected ? null : node.name);
            } else if (hasChildren) {
              toggle(node.id);
            }
          }}
          style={{
            display: 'flex',
            alignItems: 'center',
            width: '100%',
            padding: '6px 8px',
            paddingLeft: 8 + depth * 14,
            background: isSelected ? 'var(--lg-accent-bg, rgba(99,102,241,0.12))' : 'transparent',
            border: 'none',
            borderRadius: 6,
            color: 'inherit',
            cursor: 'pointer',
            textAlign: 'left',
            fontSize: 13,
            fontWeight: node.level === 0 ? 600 : 400,
          }}
        >
          {hasChildren ? (
            <span style={{ width: 14, display: 'inline-block', opacity: 0.6 }}>
              {isCollapsed ? '▶' : '▼'}
            </span>
          ) : (
            <span style={{ width: 14 }} />
          )}
          <span style={{ flex: 1, marginLeft: 4 }}>{node.name}</span>
          <span style={{ fontSize: 11, opacity: 0.7 }}>{node.user_count}</span>
        </button>
        {hasChildren && !isCollapsed && (
          <div>
            {node.children.map((c) => renderNode(c, depth + 1))}
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="lg-card" style={{ padding: 12, minHeight: 480 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
        <strong style={{ fontSize: 13 }}>조직</strong>
        <span style={{ fontSize: 11, opacity: 0.7 }}>총 {totalUsers}명</span>
      </div>
      <input
        type="text"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        placeholder="부서 검색"
        style={{
          width: '100%',
          padding: '6px 8px',
          fontSize: 12,
          background: 'var(--lg-input-bg, rgba(0,0,0,0.04))',
          border: '1px solid var(--lg-border, rgba(0,0,0,0.1))',
          borderRadius: 4,
          marginBottom: 8,
        }}
      />
      <button
        type="button"
        onClick={() => onSelectDept(null)}
        style={{
          padding: '4px 8px',
          fontSize: 11,
          background: selectedDept === null ? 'var(--lg-accent-bg, rgba(99,102,241,0.12))' : 'transparent',
          border: '1px solid var(--lg-border, rgba(0,0,0,0.1))',
          borderRadius: 4,
          marginBottom: 6,
          cursor: 'pointer',
          width: '100%',
        }}
      >
        전체 보기
      </button>
      <div style={{ maxHeight: 600, overflowY: 'auto' }}>
        {tree.map((n) => renderNode(n, 0))}
      </div>
    </div>
  );
}

export default DeptTree;
