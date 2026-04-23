/**
 * 편의 re-export — HospitalContext 훅들의 단일 import 경로.
 * 권장: `import { useHospital } from '@/hooks/useHospital'`
 */
export {
  useHospital,
  useHospitalStrict,
  useHospitalFeature,
  type HospitalContextValue,
} from '@/contexts/HospitalContext';
