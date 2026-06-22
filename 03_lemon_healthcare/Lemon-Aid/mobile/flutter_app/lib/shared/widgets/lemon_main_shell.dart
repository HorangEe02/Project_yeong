import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:go_router/go_router.dart';

import '../theme/lemon_theme.dart';

class LemonMainShell extends StatelessWidget {
  const LemonMainShell({
    super.key,
    required this.child,
    required this.currentPath,
  });

  final Widget child;
  final String currentPath;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: child,
      bottomNavigationBar: _LemonBottomBar(
        currentPath: currentPath,
        onAgentTap: () => context.go('/'),
        onChatTap: () => context.go('/chat'),
      ),
    );
  }
}

class _LemonBottomBar extends StatelessWidget {
  const _LemonBottomBar({
    required this.currentPath,
    required this.onAgentTap,
    required this.onChatTap,
  });

  final String currentPath;
  final VoidCallback onAgentTap;
  final VoidCallback onChatTap;

  @override
  Widget build(BuildContext context) {
    return DecoratedBox(
      decoration: const BoxDecoration(
        color: LemonColors.paper,
        border: Border(top: BorderSide(color: LemonColors.line)),
        boxShadow: <BoxShadow>[
          BoxShadow(
            color: Color(0x14000000),
            blurRadius: 18,
            offset: Offset(0, -4),
          ),
        ],
      ),
      child: SafeArea(
        top: false,
        child: SizedBox(
          height: 74,
          child: Row(
            children: <Widget>[
              Expanded(
                child: _NavItem(
                  icon: Icons.auto_awesome_rounded,
                  label: 'Agent',
                  active: currentPath != '/chat',
                  onTap: onAgentTap,
                ),
              ),
              Expanded(
                child: _NavItem(
                  icon: Icons.chat_bubble_rounded,
                  label: '챗봇',
                  active: currentPath == '/chat',
                  onTap: onChatTap,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _NavItem extends StatelessWidget {
  const _NavItem({
    required this.icon,
    required this.label,
    required this.active,
    required this.onTap,
  });

  final IconData icon;
  final String label;
  final bool active;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final Color color = active ? LemonColors.leaf : LemonColors.inkMuted;
    return InkWell(
      onTap: () {
        HapticFeedback.selectionClick();
        onTap();
      },
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 10),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: <Widget>[
            Icon(icon, color: color, size: active ? 27 : 24),
            const SizedBox(height: 4),
            Text(
              label,
              style: Theme.of(context).textTheme.labelMedium?.copyWith(
                    color: color,
                    fontWeight: active ? FontWeight.w800 : FontWeight.w600,
                  ),
            ),
          ],
        ),
      ),
    );
  }
}
