/**
 * Role configuration for channels page
 */

// Configure role-specific UI for channels page
function configureChannelsRoles() {
    // User role - can only view subscriptions, cannot add channels
    window.roleManager.configureRole('user', {
        showElements: ['subscriptionsList'],
        hideElements: ['addChannelButton', 'channelManagement'],
        addMessages: [
            {
                target: '.section',
                message: 'ℹ️ <strong>Только администраторы могут добавлять каналы</strong><br>Обратитесь к администратору для добавления новых каналов.',
                position: 'after'
            }
        ]
    });

    // Moderator role - can manage channels
    window.roleManager.configureRole('moderator', {
        showElements: ['subscriptionsList', 'addChannelButton', 'channelManagement'],
        hideElements: ['userManagement'],
        addMessages: []
    });

    // Admin role - full access except admin management
    window.roleManager.configureRole('admin', {
        showElements: ['subscriptionsList', 'addChannelButton', 'channelManagement', 'userManagement'],
        hideElements: [],
        addMessages: []
    });

    // Super admin - full access
    window.roleManager.configureRole('super_admin', {
        showElements: ['subscriptionsList', 'addChannelButton', 'channelManagement', 'userManagement', 'superAdminPanel'],
        hideElements: [],
        addMessages: []
    });
}

// Initialize role-based UI for channels page
async function initializeChannelsRoleUI(userId) {
    configureChannelsRoles();
    const role = await window.roleManager.initialize(userId);
    
    // Add role-specific functionality
    if (role === 'user') {
        // Hide admin features
        document.querySelectorAll('.admin-only').forEach(el => el.style.display = 'none');
    } else {
        // Show admin features
        document.querySelectorAll('.admin-only').forEach(el => el.style.display = 'block');
    }
    
    return role;
}




