import 'package:flutter/material.dart';

class AppLocalizations {
  final Locale locale;
  AppLocalizations(this.locale);

  static AppLocalizations of(BuildContext context) {
    return Localizations.of<AppLocalizations>(context, AppLocalizations)!;
  }

  static const LocalizationsDelegate<AppLocalizations> delegate = _AppLocalizationsDelegate();

  static final Map<String, Map<String, String>> _translations = {
    'en': {
      'app_name': 'AfriMine AI',
      'welcome': 'Welcome to AfriMine AI',
      'onboard_title1': 'Detect Minerals with AI',
      'onboard_desc1': 'Take a photo of your sample and let our AI identify potential minerals instantly.',
      'onboard_title2': 'Works Offline',
      'onboard_desc2': 'Capture samples even without internet. Data syncs automatically when you reconnect.',
      'onboard_title3': 'Track Your Land Value',
      'onboard_desc3': 'Monitor mineral deposits on your land and get real-time market estimates.',
      'get_started': 'Get Started',
      'next': 'Next',
      'skip': 'Skip',
      'login': 'Login',
      'phone_number': 'Phone Number',
      'enter_phone': 'Enter your phone number',
      'send_otp': 'Send OTP',
      'verify_otp': 'Verify OTP',
      'enter_otp': 'Enter the 6-digit code',
      'resend_otp': 'Resend OTP',
      'dashboard': 'Dashboard',
      'my_land': 'My Land',
      'estimated_value': 'Estimated Value',
      'total_samples': 'Total Samples',
      'quick_actions': 'Quick Actions',
      'new_sample': 'New Sample',
      'view_map': 'View Map',
      'market_prices': 'Market Prices',
      'recent_samples': 'Recent Samples',
      'view_all': 'View All',
      'capture_sample': 'Capture Sample',
      'take_photo': 'Take Photo',
      'gallery': 'Gallery',
      'gps_location': 'GPS Location',
      'field_tests': 'Field Tests',
      'notes': 'Notes',
      'submit_sample': 'Submit Sample',
      'sample_list': 'My Samples',
      'all': 'All',
      'pending': 'Pending',
      'analyzed': 'Analyzed',
      'verified': 'Verified',
      'search_samples': 'Search samples...',
      'no_samples': 'No samples yet',
      'no_samples_desc': 'Capture your first mineral sample to get started.',
      'sample_detail': 'Sample Details',
      'photo': 'Photo',
      'classification': 'AI Classification',
      'confidence': 'Confidence',
      'grade_estimate': 'Grade Estimate',
      'location': 'Location',
      'field_test_results': 'Field Test Results',
      'satellite_map': 'Satellite Map',
      'samples_on_map': 'Samples on Map',
      'alteration_overlay': 'Alteration Overlay',
      'reports': 'Reports',
      'generate_report': 'Generate Report',
      'investor_report': 'Investor Report',
      'summary_report': 'Summary Report',
      'detailed_report': 'Detailed Report',
      'share_report': 'Share Report',
      'download_pdf': 'Download PDF',
      'gold_price': 'Gold Price',
      'copper_price': 'Copper Price',
      'price_per_oz': 'per oz',
      'price_change': '24h Change',
      'settings': 'Settings',
      'language': 'Language',
      'english': 'English',
      'swahili': 'Kiswahili',
      'offline_mode': 'Offline Mode',
      'offline_mode_desc': 'Auto-sync when connected',
      'sync_status': 'Sync Status',
      'last_sync': 'Last Sync',
      'sync_now': 'Sync Now',
      'syncing': 'Syncing...',
      'sync_complete': 'Sync Complete',
      'sync_failed': 'Sync Failed',
      'about': 'About',
      'logout': 'Logout',
      'cancel': 'Cancel',
      'save': 'Save',
      'delete': 'Delete',
      'edit': 'Edit',
      'close': 'Close',
      'confirm': 'Confirm',
      'loading': 'Loading...',
      'error': 'Error',
      'success': 'Success',
      'retry': 'Retry',
      'no_internet': 'No Internet Connection',
      'offline_data_saved': 'Data saved offline. Will sync when connected.',
    },
    'sw': {
      'app_name': 'AfriMine AI',
      'welcome': 'Karibu AfriMine AI',
      'onboard_title1': 'Gundua Madini kwa AI',
      'onboard_desc1': 'Piga picha ya sampuli yako na AI yetu itambue madini yanayowezekana mara moja.',
      'onboard_title2': 'Inafanya Bila Mtandao',
      'onboard_desc2': 'Piga sampuli hata bila mtandao. Data inasawazishwa kiotomatiki unapounganisha tena.',
      'onboard_title3': 'Fuatilia Thamani ya Ardhi Yako',
      'onboard_desc3': 'Fuatilia amana za madini kwenye ardhi yako na upate makadirio ya soko ya wakati halisi.',
      'get_started': 'Anza',
      'next': 'Ifuatayo',
      'skip': 'Ruka',
      'login': 'Ingia',
      'phone_number': 'Nambari ya Simu',
      'enter_phone': 'Weka nambari yako ya simu',
      'send_otp': 'Tuma OTP',
      'verify_otp': 'Thibitisha OTP',
      'enter_otp': 'Weka nambari ya tarakimu 6',
      'resend_otp': 'Tuma OTP Tena',
      'dashboard': 'Dashibodi',
      'my_land': 'Ardhi Yangu',
      'estimated_value': 'Thamani Inayokadiriwa',
      'total_samples': 'Sampuli Zote',
      'quick_actions': 'Haraka',
      'new_sample': 'Sampuli Mpya',
      'view_map': 'Tazama Ramani',
      'market_prices': 'Bei za Soko',
      'recent_samples': 'Sampuli za Hivi Karibuni',
      'view_all': 'Tazama Zote',
      'capture_sample': 'Piga Sampuli',
      'take_photo': 'Piga Picha',
      'gallery': 'Galeri',
      'gps_location': 'Mahali GPS',
      'field_tests': 'Majaribio ya Shamba',
      'notes': 'Vidokezo',
      'submit_sample': 'Wasilisha Sampuli',
      'sample_list': 'Sampuli Zangu',
      'all': 'Zote',
      'pending': 'Inasubiri',
      'analyzed': 'Imechambuliwa',
      'verified': 'Imethibitishwa',
      'search_samples': 'Tafuta sampuli...',
      'no_samples': 'Hakuna sampuli bado',
      'no_samples_desc': 'Piga sampuli yako ya kwanza ya madini kuanza.',
      'sample_detail': 'Maelezo ya Sampuli',
      'photo': 'Picha',
      'classification': 'Uainishaji wa AI',
      'confidence': 'Ujasiri',
      'grade_estimate': 'Kadirio la Daraja',
      'location': 'Mahali',
      'field_test_results': 'Matokeo ya Majaribio',
      'satellite_map': 'Ramani ya Satelaiti',
      'samples_on_map': 'Sampuli kwenye Ramani',
      'alteration_overlay': 'Mabadiliko ya Ramani',
      'reports': 'Ripoti',
      'generate_report': 'Tengeneza Ripoti',
      'investor_report': 'Ripoti ya Mwekezaji',
      'summary_report': 'Ripoti ya Muhtasari',
      'detailed_report': 'Ripoti ya Kina',
      'share_report': 'Shiriki Ripoti',
      'download_pdf': 'Pakua PDF',
      'gold_price': 'Bei ya Dhahabu',
      'copper_price': 'Bei ya Shaba',
      'price_per_oz': 'kwa oz',
      'price_change': 'Mabadiliko 24h',
      'settings': 'Mipangilio',
      'language': 'Lugha',
      'english': 'English',
      'swahili': 'Kiswahili',
      'offline_mode': 'Hali ya Nje ya Mtandao',
      'offline_mode_desc': 'Sawazisha kiotomatiki unapounganishwa',
      'sync_status': 'Hali ya Kusawazisha',
      'last_sync': 'Sawazisha ya Mwisho',
      'sync_now': 'Sawazisha Sasa',
      'syncing': 'Inasawazisha...',
      'sync_complete': 'Kusawazisha Kumekamilika',
      'sync_failed': 'Kusawazisha Kumeshindwa',
      'about': 'Kuhusu',
      'logout': 'Ondoka',
      'cancel': 'Ghairi',
      'save': 'Hifadhi',
      'delete': 'Futa',
      'edit': 'Hariri',
      'close': 'Funga',
      'confirm': 'Thibitisha',
      'loading': 'Inapakia...',
      'error': 'Hitilafu',
      'success': 'Imefanikiwa',
      'retry': 'Jaribu Tena',
      'no_internet': 'Hakuna Muungano wa Mtandao',
      'offline_data_saved': 'Data imehifadhiwa nje ya mtandao. Itasawazishwa unapounganishwa.',
    },
  };

  String translate(String key) {
    return _translations[locale.languageCode]?[key] ?? _translations['en']?[key] ?? key;
  }

  // Convenience getters
  String get appName => translate('app_name');
  String get welcome => translate('welcome');
  String get dashboard => translate('dashboard');
  String get settings => translate('settings');
  String get newSample => translate('new_sample');
  String get sampleList => translate('sample_list');
  String get reports => translate('reports');
  String get marketPrices => translate('market_prices');
  String get satelliteMap => translate('satellite_map');
  String get captureSample => translate('capture_sample');
  String get submitSample => translate('submit_sample');
  String get logout => translate('logout');
  String get cancel => translate('cancel');
  String get save => translate('save');
  String get retry => translate('retry');
  String get loading => translate('loading');
}

class _AppLocalizationsDelegate extends LocalizationsDelegate<AppLocalizations> {
  const _AppLocalizationsDelegate();

  @override
  bool isSupported(Locale locale) => ['en', 'sw'].contains(locale.languageCode);

  @override
  Future<AppLocalizations> load(Locale locale) async => AppLocalizations(locale);

  @override
  bool shouldReload(_AppLocalizationsDelegate old) => false;
}
