class ConfirmedFoodEntry {
  ConfirmedFoodEntry({
    required this.name,
    required this.mealType,
    required this.servingLabel,
    required this.memo,
    required this.photoName,
  });

  final String name;
  final String mealType;
  final String servingLabel;
  final String memo;
  final String? photoName;

  Map<String, dynamic> toAgentFoodJson() {
    return <String, dynamic>{
      'name': name,
      'meal_type': mealType,
      if (servingLabel.isNotEmpty) 'serving_label': servingLabel,
      if (memo.isNotEmpty) 'memo': memo,
      if (photoName != null && photoName!.isNotEmpty) 'photo_name': photoName,
    };
  }

  Map<String, dynamic> toAgentSourceJson() {
    return <String, dynamic>{
      'source_type': 'food_user_input',
      if (photoName != null && photoName!.isNotEmpty) 'image_id': photoName,
      'user_confirmed': true,
    };
  }
}
