import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:image_picker/image_picker.dart';
import 'package:permission_handler/permission_handler.dart';

import '../../../shared/state/confirmed_entry_store.dart';
import '../../../shared/theme/lemon_theme.dart';
import '../../../shared/widgets/capture_frame_card.dart';
import '../../../shared/widgets/medical_disclaimer.dart';
import '../domain/confirmed_food_entry.dart';

class FoodCaptureScreen extends StatefulWidget {
  const FoodCaptureScreen({super.key});

  @override
  State<FoodCaptureScreen> createState() => _FoodCaptureScreenState();
}

class _FoodCaptureScreenState extends State<FoodCaptureScreen> {
  final ImagePicker _picker = ImagePicker();
  final TextEditingController _foodNameController = TextEditingController();
  final TextEditingController _mealTypeController =
      TextEditingController(text: 'lunch');
  final TextEditingController _servingLabelController = TextEditingController();
  final TextEditingController _memoController = TextEditingController();

  String? _selectedImageName;
  String? _statusMessage;
  bool _isSelecting = false;
  bool userConfirmed = false;
  ConfirmedFoodEntry? _lastConfirmedEntry;

  @override
  void dispose() {
    _foodNameController.dispose();
    _mealTypeController.dispose();
    _servingLabelController.dispose();
    _memoController.dispose();
    super.dispose();
  }

  Future<void> _selectImage(ImageSource source) async {
    setState(() {
      _isSelecting = true;
      _statusMessage = null;
      userConfirmed = false;
    });

    try {
      if (source == ImageSource.camera) {
        final PermissionStatus status = await Permission.camera.request();
        if (!status.isGranted) {
          if (!mounted) {
            return;
          }
          setState(() {
            _statusMessage = 'Camera permission is required.';
          });
          return;
        }
      }

      final XFile? image = await _picker.pickImage(
        source: source,
        imageQuality: 92,
      );
      if (!mounted) {
        return;
      }
      setState(() {
        _selectedImageName = image?.name;
        _statusMessage =
            image == null ? 'No food image selected.' : 'Food image selected.';
      });
    } catch (_) {
      if (!mounted) {
        return;
      }
      setState(() {
        _statusMessage = 'Could not load the food image.';
      });
    } finally {
      if (mounted) {
        setState(() {
          _isSelecting = false;
        });
      }
    }
  }

  void _confirmFoodInput() {
    final ConfirmedFoodEntry? entry = _confirmedForAgentPayload();
    if (entry == null) {
      setState(() {
        _statusMessage =
            'Confirm the food name and meal type before using this entry.';
      });
      return;
    }

    setState(() {
      ConfirmedEntryStore.instance.addFood(entry);
      _lastConfirmedEntry = entry;
      _statusMessage = 'Confirmed food entry is ready for AI coaching.';
    });
    context.go(
      '/entry-result'
      '?type=food'
      '&title=${Uri.encodeComponent(entry.name)}'
      '&subtitle=${Uri.encodeComponent('${entry.mealType} 기록이 코칭 근거로 준비되었습니다.')}'
      '&detail1=${Uri.encodeComponent('끼니: ${entry.mealType}')}'
      '&detail2=${Uri.encodeComponent(entry.servingLabel.isEmpty ? '섭취량: 미입력' : '섭취량: ${entry.servingLabel}')}'
      '&detail3=${Uri.encodeComponent(entry.photoName == null ? '사진: 미선택' : '사진: ${entry.photoName}')}',
    );
  }

  ConfirmedFoodEntry? _confirmedForAgentPayload() {
    final String foodName = _foodNameController.text.trim();
    final String mealType = _mealTypeController.text.trim();
    if (!userConfirmed || foodName.isEmpty || mealType.isEmpty) {
      return null;
    }
    return ConfirmedFoodEntry(
      name: foodName,
      mealType: mealType,
      servingLabel: _servingLabelController.text.trim(),
      memo: _memoController.text.trim(),
      photoName: _selectedImageName,
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.fromLTRB(16, 18, 16, 28),
          children: <Widget>[
            Row(
              children: <Widget>[
                IconButton(
                  onPressed: () => context.go('/'),
                  icon: const Icon(Icons.arrow_back_rounded),
                ),
                Expanded(
                  child: Text(
                    '음식 입력',
                    style: Theme.of(context).textTheme.headlineSmall,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 10),
            LemonCard(
              color: LemonColors.leafSoft,
              child: Row(
                children: <Widget>[
                  const Icon(
                    Icons.restaurant_menu_rounded,
                    color: LemonColors.leaf,
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Text(
                      '음식 모델 연결 전에는 사용자가 확인한 입력만 코칭 근거로 사용합니다.',
                      style: Theme.of(context).textTheme.bodyMedium,
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 16),
            CaptureFrameCard(
              title: '음식 사진',
              subtitle: '음식이 프레임 안에 들어오게 촬영하거나 앨범에서 선택해 주세요.',
              icon: Icons.restaurant_menu_rounded,
              accentColor: LemonColors.leaf,
              selectedImageName: _selectedImageName,
              isSelecting: _isSelecting,
              onPick: _selectImage,
            ),
            const SizedBox(height: 16),
            LemonCard(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  if (_selectedImageName != null) ...<Widget>[
                    LemonPill(
                      label: _selectedImageName!,
                      color: LemonColors.sky,
                      backgroundColor: LemonColors.skySoft,
                    ),
                    const SizedBox(height: 12),
                  ],
                  TextField(
                    controller: _foodNameController,
                    decoration: const InputDecoration(labelText: '음식명'),
                  ),
                  const SizedBox(height: 10),
                  TextField(
                    controller: _mealTypeController,
                    decoration: const InputDecoration(labelText: '끼니'),
                  ),
                  const SizedBox(height: 10),
                  TextField(
                    controller: _servingLabelController,
                    decoration: const InputDecoration(labelText: '섭취량'),
                  ),
                  const SizedBox(height: 10),
                  TextField(
                    controller: _memoController,
                    decoration: const InputDecoration(labelText: '메모'),
                  ),
                  CheckboxListTile(
                    contentPadding: EdgeInsets.zero,
                    value: userConfirmed,
                    onChanged: (bool? value) {
                      setState(() {
                        userConfirmed = value ?? false;
                      });
                    },
                    title: const Text('이 음식 입력을 확인했습니다.'),
                  ),
                  FilledButton.icon(
                    onPressed: _confirmFoodInput,
                    icon: const Icon(Icons.check_circle_outline),
                    label: const Text('Confirm food entry'),
                  ),
                ],
              ),
            ),
            if (_statusMessage != null) ...<Widget>[
              const SizedBox(height: 12),
              Text(_statusMessage!),
            ],
            if (_lastConfirmedEntry != null) ...<Widget>[
              const SizedBox(height: 12),
              LemonCard(
                color: LemonColors.lemonSoft,
                child: Text(
                  'Ready: ${_lastConfirmedEntry!.name} (${_lastConfirmedEntry!.mealType})',
                  style: Theme.of(context).textTheme.titleMedium,
                ),
              ),
            ],
            const SizedBox(height: 24),
            const MedicalDisclaimer(),
          ],
        ),
      ),
    );
  }
}
