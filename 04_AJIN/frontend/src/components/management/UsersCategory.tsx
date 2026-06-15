// UsersCategory.tsx — v4.8 F-Users.
// 좌측 DeptTree + 우측 UserList(간이) + 상단 "CSV 업로드" / "일괄 변경" 버튼.
// v4.9 이후 admin/tabs/UsersTab 은 제거됨 (PR-E4). 본 카테고리는 부서 선택 기반의 가벼운 뷰.

import { useEffect, useMemo, useState } from 'react';
import { useAuthStore } from '@store/auth';
import { fetchDirectoryTree, type DirectoryNode } from '@api/management';
import {
  fetchDepartmentTree,
  fetchUsers,
  type AdminUserItem,
  type DepartmentTreeResponse,
} from '@api/admin';
import { CreateUserModal } from '@components/admin/CreateUserModal';
import { DeptTree } from './DeptTree';
import { UserBulkUpload } from './UserBulkUpload';
import { BulkRoleChangeModal } from './BulkRoleChangeModal';

export function UsersCategory() {
  const auth = useAuthStore((s) => s.user);
  const myLevel = auth?.role_level ?? 1;
  const canBulk = myLevel >= 4;

  const [nodes, setNodes] = useState<DirectoryNode[]>([]);
  const [totalUsers, setTotalUsers] = useState(0);
  const [loading, setLoading] = useState(true);
  const [treeError, setTreeError] = useState<string | null>(null);

  const [selectedDept, setSelectedDept] = useState<string | null>(null);
  const [users, setUsers] = useState<AdminUserItem[]>([]);
  const [usersLoading, setUsersLoading] = useState(false);
  const [usersError, setUsersError] = useState<string | null>(null);

  const [adminTree, setAdminTree] = useState<DepartmentTreeResponse | null>(null);
  const [adminTreeError, setAdminTreeError] = useState<string | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [showUpload, setShowUpload] = useState(false);
  const [showRoleModal, setShowRoleModal] = useState(false);
  const [showCreateUser, setShowCreateUser] = useState(false);

  // 1) 부서 트리 로드
  useEffect(() => {
    setLoading(true);
    fetchDirectoryTree()
      .then((r) => {
        setNodes(r.nodes);
        setTotalUsers(r.total_users);
        setTreeError(null);
      })
      .catch((e) => setTreeError((e as Error)?.message || '부서 트리 로드 실패'))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (myLevel < 4) {
      setAdminTree(null);
      return;
    }
    fetchDepartmentTree()
      .then((r) => {
        setAdminTree(r);
        setAdminTreeError(null);
      })
      .catch((e) => setAdminTreeError((e as Error)?.message || '계정 발급 기준 데이터 로드 실패'));
  }, [myLevel]);

  // 2) 사용자 목록 로드 (HR_ADMIN+ only).
  useEffect(() => {
    if (myLevel < 4) {
      setUsers([]);
      return;
    }
    setUsersLoading(true);
    setUsersError(null);
    fetchUsers({
      department: selectedDept || undefined,
      status: 'active',
      limit: 500,
    })
      .then((r) => setUsers(r.users))
      .catch((e) => setUsersError((e as Error)?.message || '사용자 로드 실패'))
      .finally(() => setUsersLoading(false));
  }, [selectedDept, myLevel]);

  const toggleSelect = (employeeId: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(employeeId)) next.delete(employeeId);
      else next.add(employeeId);
      return next;
    });
  };

  const toggleAll = () => {
    if (selected.size === users.length) {
      setSelected(new Set());
    } else {
      setSelected(new Set(users.map((u) => u.employee_id)));
    }
  };

  const selectedIds = useMemo(() => [...selected], [selected]);

  const reloadUsers = () => {
    if (myLevel < 4) return;
    setUsersLoading(true);
    setUsersError(null);
    fetchUsers({
      department: selectedDept || undefined,
      status: 'active',
      limit: 500,
    })
      .then((r) => setUsers(r.users))
      .catch((e) => setUsersError((e as Error)?.message || '사용자 로드 실패'))
      .finally(() => setUsersLoading(false));
  };

  const reloadDirectoryTree = () => {
    setLoading(true);
    fetchDirectoryTree()
      .then((r) => {
        setNodes(r.nodes);
        setTotalUsers(r.total_users);
        setTreeError(null);
      })
      .catch((e) => setTreeError((e as Error)?.message || '부서 트리 로드 실패'))
      .finally(() => setLoading(false));
  };

  const handleCreateModalClose = () => {
    setShowCreateUser(false);
    reloadDirectoryTree();
    reloadUsers();
  };

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '280px 1fr', gap: 16 }}>
      <div>
        {loading ? (
          <div className="lg-card" style={{ padding: 12, fontSize: 12 }}>로딩 중…</div>
        ) : treeError ? (
          <div className="lg-card" style={{ padding: 12 }}>
            <div className="lg-state-pill crit">{treeError}</div>
          </div>
        ) : (
          <DeptTree
            nodes={nodes}
            totalUsers={totalUsers}
            selectedDept={selectedDept}
            onSelectDept={setSelectedDept}
          />
        )}
      </div>

      <div>
        <div className="lg-card-h" style={{ marginBottom: 12 }}>
          <div>
            <strong>{selectedDept ?? '전체 사용자'}</strong>
            <span style={{ fontSize: 11, opacity: 0.6, marginLeft: 8 }}>
              {users.length}명{selected.size > 0 ? ` · ${selected.size}명 선택` : ''}
            </span>
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            {canBulk && (
              <>
                <button
                  type="button"
                  className="lg-btn lg-btn-primary"
                  onClick={() => setShowCreateUser(true)}
                  disabled={!adminTree}
                  title={adminTreeError ?? ''}
                >
                  + 신입사원 추가
                </button>
                <button
                  type="button"
                  className="lg-btn"
                  onClick={() => setShowUpload((v) => !v)}
                >
                  {showUpload ? '업로드 패널 닫기' : 'CSV 업로드'}
                </button>
                <button
                  type="button"
                  className="lg-btn lg-btn-primary"
                  onClick={() => setShowRoleModal(true)}
                  disabled={selected.size === 0}
                >
                  일괄 권한 변경 ({selected.size})
                </button>
              </>
            )}
          </div>
        </div>

        {showUpload && canBulk && (
          <div style={{ marginBottom: 12 }}>
            <UserBulkUpload />
          </div>
        )}

        {adminTreeError && canBulk && (
          <div className="lg-state-pill warn" style={{ marginBottom: 12 }}>
            신입사원 추가 기준 데이터 로드 실패: {adminTreeError}
          </div>
        )}

        <div className="lg-card" style={{ padding: 0 }}>
          {myLevel < 4 ? (
            <div style={{ padding: 16, fontSize: 12, opacity: 0.7 }}>
              사용자 상세 목록은 L4(HR_ADMIN) 이상에서만 표시됩니다. 좌측 부서 트리에서 조직 헤드카운트만 확인할 수 있습니다.
            </div>
          ) : usersLoading ? (
            <div style={{ padding: 16, fontSize: 12 }}>로딩 중…</div>
          ) : usersError ? (
            <div style={{ padding: 16 }}>
              <div className="lg-state-pill crit">{usersError}</div>
            </div>
          ) : users.length === 0 ? (
            <div style={{ padding: 16, fontSize: 12, opacity: 0.7 }}>해당 조건의 사용자가 없습니다.</div>
          ) : (
            <table style={{ width: '100%', fontSize: 12, borderCollapse: 'collapse' }}>
              <thead>
                <tr>
                  <th style={th}>
                    <input
                      type="checkbox"
                      checked={selected.size === users.length && users.length > 0}
                      onChange={toggleAll}
                    />
                  </th>
                  <th style={th}>사번</th>
                  <th style={th}>이름</th>
                  <th style={th}>부서</th>
                  <th style={th}>직급</th>
                  <th style={th}>역할</th>
                  <th style={th}>레벨</th>
                </tr>
              </thead>
              <tbody>
                {users.map((u) => (
                  <tr key={u.employee_id}>
                    <td style={td}>
                      <input
                        type="checkbox"
                        checked={selected.has(u.employee_id)}
                        onChange={() => toggleSelect(u.employee_id)}
                      />
                    </td>
                    <td style={td}>{u.employee_id}</td>
                    <td style={td}>{u.username}</td>
                    <td style={td}>{u.department}</td>
                    <td style={td}>{u.position}</td>
                    <td style={td}>{u.role_name}</td>
                    <td style={td}>L{u.role_level}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {showRoleModal && (
        <BulkRoleChangeModal
          userIds={selectedIds}
          onClose={() => setShowRoleModal(false)}
          onApplied={() => {
            // 적용 후 사용자 목록 새로고침
            if (myLevel >= 4) {
              fetchUsers({
                department: selectedDept || undefined,
                status: 'active',
                limit: 500,
              }).then((r) => setUsers(r.users));
            }
            setSelected(new Set());
          }}
        />
      )}

      {showCreateUser && canBulk && (
        <CreateUserModal
          isOpen={showCreateUser}
          onClose={handleCreateModalClose}
          tree={adminTree}
          onCreated={() => {
            reloadDirectoryTree();
            reloadUsers();
            setSelected(new Set());
          }}
        />
      )}
    </div>
  );
}

const th: React.CSSProperties = {
  textAlign: 'left',
  padding: '6px 10px',
  borderBottom: '1px solid var(--lg-border, rgba(0,0,0,0.1))',
  fontWeight: 600,
  fontSize: 11,
  opacity: 0.7,
};

const td: React.CSSProperties = {
  textAlign: 'left',
  padding: '6px 10px',
  borderBottom: '1px solid var(--lg-border-soft, rgba(0,0,0,0.05))',
};

export default UsersCategory;
