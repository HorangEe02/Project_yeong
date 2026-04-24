/** 동선 템플릿 */
export interface RouteTemplate {
  id: string;
  name: string;
  departmentTag: string;
  color: string;
  waypointPoiIds: string[];
  estimatedTotalTime: number;
  isDefault: boolean;
}
