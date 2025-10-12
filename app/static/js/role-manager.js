/**
 * Role-based UI management system
 * Manages what UI elements are shown/hidden based on user roles
 */

class RoleManager {
    constructor() {
        this.currentRole = null;
        this.roleConfigs = {
            user: {
                showElements: [],
                hideElements: [],
                addMessages: [],
                permissions: ['view_filters', 'edit_filters']
            },
            moderator: {
                showElements: [],
                hideElements: [],
                addMessages: [],
                permissions: ['view_filters', 'edit_filters', 'manage_channels']
            },
            admin: {
                showElements: [],
                hideElements: [],
                addMessages: [],
                permissions: ['view_filters', 'edit_filters', 'manage_channels', 'manage_users']
            },
            super_admin: {
                showElements: [],
                hideElements: [],
                addMessages: [],
                permissions: ['view_filters', 'edit_filters', 'manage_channels', 'manage_users', 'manage_admins']
            }
        };
    }

    /**
     * Check if user has specific permission
     */
    hasPermission(permission) {
        if (!this.currentRole) return false;
        return this.roleConfigs[this.currentRole].permissions.includes(permission);
    }

    /**
     * Check if user has admin rights
     */
    isAdmin() {
        return this.currentRole && ['moderator', 'admin', 'super_admin'].includes(this.currentRole);
    }

    /**
     * Set current user role
     */
    setRole(role) {
        this.currentRole = role;
    }

    /**
     * Apply role-based UI changes
     */
    applyRoleUI() {
        if (!this.currentRole) return;

        const config = this.roleConfigs[this.currentRole];
        
        // Show/hide elements
        config.showElements.forEach(elementId => {
            const element = document.getElementById(elementId);
            if (element) {
                element.style.display = 'block';
            }
        });
        
        config.hideElements.forEach(elementId => {
            const element = document.getElementById(elementId);
            if (element) {
                element.style.display = 'none';
            }
        });
        
        // Add role-specific messages
        config.addMessages.forEach(messageConfig => {
            this.addMessage(messageConfig);
        });
    }

    /**
     * Add role-specific message to UI
     */
    addMessage(messageConfig) {
        const target = document.querySelector(messageConfig.target);
        if (target) {
            const messageDiv = document.createElement('div');
            messageDiv.className = 'role-message';
            messageDiv.style.cssText = messageConfig.style || 'text-align: center; margin: 20px 0; padding: 15px; background: var(--tg-theme-secondary-bg-color, #f8f9fa); border-radius: 8px; color: var(--tg-theme-hint-color, #666666);';
            messageDiv.innerHTML = messageConfig.message;
            
            if (messageConfig.position === 'after') {
                target.appendChild(messageDiv);
            } else {
                target.insertBefore(messageDiv, target.firstChild);
            }
        }
    }

    /**
     * Configure role-specific UI elements
     */
    configureRole(role, config) {
        this.roleConfigs[role] = { ...this.roleConfigs[role], ...config };
    }

    /**
     * Initialize role manager with user ID
     */
    async initialize(userId) {
        try {
            const response = await fetch(`/api/v1/admin/check-rights?user_id=${userId}`);
            const data = await response.json();
            
            if (data.is_admin) {
                // For now, we'll determine role based on permissions
                // In the future, we can get the actual role from the API
                this.setRole('admin');
            } else {
                this.setRole('user');
            }
            
            this.applyRoleUI();
            return this.currentRole;
        } catch (error) {
            console.error('Error initializing role manager:', error);
            this.setRole('user');
            this.applyRoleUI();
            return 'user';
        }
    }
}

// Global instance
window.roleManager = new RoleManager();




