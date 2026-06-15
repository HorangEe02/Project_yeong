// CreateUserModal — 신입사원 ID 발급 모달 (v4.9.5).
//
// CreateUserForm 을 Modal 로 wrap. v4.9 이후 AccountDelegationTab 에서 호출 예정 (PR-E5+).

import { Modal } from '@components/ui/Modal';
import { CreateUserForm } from '@components/admin/CreateUserForm';
import type { CreateEmployeeResponse, DepartmentTreeResponse } from '@api/admin';

interface Props {
  isOpen: boolean;
  onClose: () => void;
  tree: DepartmentTreeResponse | null;
  onCreated: (result: CreateEmployeeResponse) => void;
}

export function CreateUserModal({ isOpen, onClose, tree, onCreated }: Props) {
  return (
    <Modal isOpen={isOpen} onClose={onClose} title="+ 신입사원 추가" size="lg">
      <CreateUserForm
        tree={tree}
        onCreated={onCreated}
        onCancel={onClose}
        onResultClose={onClose}
      />
    </Modal>
  );
}
