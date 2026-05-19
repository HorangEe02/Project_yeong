/// 응급 자원 위젯 — 백엔드 응답의 emergency_resources 또는 자체 fallback.
///
/// 백엔드가 응답을 비워 보내도 자체 fallback (정신건강위기상담 1577-0199 /
/// 자살예방 109 / 응급의료 1339) 으로 사용자에게 항상 가시 — Rule 1
/// (모든 권고 화면 안전 안내 보장).
///
/// 전화 호출: ``url_launcher`` 의 ``tel:`` scheme. M-4 에서 canLaunchUrl
/// 분기 + Clipboard 복사 가시 처리 추가.
library;

import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

import '../models/emergency_contact.dart';

/// M-1 자체 안전 안내 본문 — 백엔드 응답 비어있을 때 사용.
const List<EmergencyContact> _defaultEmergencyContacts = <EmergencyContact>[
  EmergencyContact(name: '정신건강위기상담', phone: '1577-0199'),
  EmergencyContact(name: '자살예방상담', phone: '109'),
  EmergencyContact(name: '응급의료정보', phone: '1339'),
];

class EmergencyResources extends StatelessWidget {
  const EmergencyResources({super.key, this.items});

  /// 백엔드 ``emergency_resources`` 응답. ``null`` 또는 빈 리스트면 자체 본문.
  final List<EmergencyContact>? items;

  @override
  Widget build(BuildContext context) {
    final List<EmergencyContact> contacts =
        (items == null || items!.isEmpty) ? _defaultEmergencyContacts : items!;
    final ThemeData theme = Theme.of(context);

    return Card(
      color: theme.colorScheme.errorContainer,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Row(
              children: <Widget>[
                Icon(Icons.local_hospital, color: theme.colorScheme.onErrorContainer),
                const SizedBox(width: 8),
                Text(
                  '긴급 도움',
                  style: theme.textTheme.titleSmall?.copyWith(
                    color: theme.colorScheme.onErrorContainer,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            for (final EmergencyContact contact in contacts)
              _ContactTile(contact: contact),
          ],
        ),
      ),
    );
  }
}

class _ContactTile extends StatelessWidget {
  const _ContactTile({required this.contact});

  final EmergencyContact contact;

  @override
  Widget build(BuildContext context) {
    final ThemeData theme = Theme.of(context);
    return Semantics(
      label: '응급 자원 ${contact.name} 전화 ${contact.phone}',
      button: true,
      child: InkWell(
        onTap: () => _onTap(context, contact.phone),
        borderRadius: BorderRadius.circular(8),
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: 8),
          child: Row(
            children: <Widget>[
              Icon(Icons.phone, size: 20, color: theme.colorScheme.onErrorContainer),
              const SizedBox(width: 12),
              Expanded(
                child: Text(
                  contact.name,
                  style: theme.textTheme.bodyMedium?.copyWith(
                    color: theme.colorScheme.onErrorContainer,
                  ),
                ),
              ),
              Text(
                contact.phone,
                style: theme.textTheme.bodyMedium?.copyWith(
                  color: theme.colorScheme.onErrorContainer,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Future<void> _onTap(BuildContext context, String phone) async {
    // M-1: tel: scheme 시도. canLaunchUrl 미지원 분기 + Clipboard 복사는 M-4.
    final Uri uri = Uri(scheme: 'tel', path: phone);
    await launchUrl(uri);
  }
}
