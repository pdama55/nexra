import type { UserRole } from '../types';

interface PermissionMap {
  viewAll: boolean;
  exportAudit: boolean;
  generateCompliance: boolean;
  approveHitl: boolean;
  quarantineAgent: boolean;
  createPolicy: boolean;
  manageApiKeys: boolean;
  manageTeam: boolean;
  configureWebhooks: boolean;
  viewBilling: boolean;
  deleteOrg: boolean;
}

const PERMISSIONS: Record<UserRole, PermissionMap> = {
  admin: {
    viewAll: true,
    exportAudit: true,
    generateCompliance: true,
    approveHitl: true,
    quarantineAgent: true,
    createPolicy: true,
    manageApiKeys: true,
    manageTeam: true,
    configureWebhooks: true,
    viewBilling: true,
    deleteOrg: true,
  },
  engineer: {
    viewAll: true,
    exportAudit: true,
    generateCompliance: true,
    approveHitl: true,
    quarantineAgent: true,
    createPolicy: false,
    manageApiKeys: false,
    manageTeam: false,
    configureWebhooks: false,
    viewBilling: false,
    deleteOrg: false,
  },
  compliance: {
    viewAll: true,
    exportAudit: true,
    generateCompliance: true,
    approveHitl: false,
    quarantineAgent: false,
    createPolicy: false,
    manageApiKeys: false,
    manageTeam: false,
    configureWebhooks: false,
    viewBilling: false,
    deleteOrg: false,
  },
  viewer: {
    viewAll: true,
    exportAudit: false,
    generateCompliance: false,
    approveHitl: false,
    quarantineAgent: false,
    createPolicy: false,
    manageApiKeys: false,
    manageTeam: false,
    configureWebhooks: false,
    viewBilling: false,
    deleteOrg: false,
  },
};

export function getPermissions(role: UserRole): PermissionMap {
  return PERMISSIONS[role];
}

export function hasPermission(role: UserRole, action: keyof PermissionMap): boolean {
  return PERMISSIONS[role][action];
}
