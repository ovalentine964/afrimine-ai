import 'package:supabase_flutter/supabase_flutter.dart';
import '../utils/constants.dart';

class AuthService {
  static AuthService? _instance;
  final SupabaseClient _client = Supabase.instance.client;

  AuthService._();

  factory AuthService() {
    _instance ??= AuthService._();
    return _instance!;
  }

  SupabaseClient get client => _client;
  User? get currentUser => _client.auth.currentUser;
  bool get isLoggedIn => currentUser != null;
  String? get userId => currentUser?.id;

  Stream<AuthState> get authStateChanges => _client.auth.onAuthStateChange;

  // Phone + OTP Authentication
  Future<void> sendOtp(String phoneNumber) async {
    // Format phone number - ensure it starts with +
    String formatted = phoneNumber.trim();
    if (!formatted.startsWith('+')) {
      // Assume Kenya number if no country code
      if (formatted.startsWith('0')) {
        formatted = '+254${formatted.substring(1)}';
      } else {
        formatted = '+254$formatted';
      }
    }

    await _client.auth.signInWithOtp(phone: formatted);
  }

  Future<AuthResponse> verifyOtp(String phoneNumber, String otp) async {
    String formatted = phoneNumber.trim();
    if (!formatted.startsWith('+')) {
      if (formatted.startsWith('0')) {
        formatted = '+254${formatted.substring(1)}';
      } else {
        formatted = '+254$formatted';
      }
    }

    final response = await _client.auth.verifyOTP(
      phone: formatted,
      token: otp,
      type: OtpType.sms,
    );
    return response;
  }

  Future<void> signOut() async {
    await _client.auth.signOut();
  }

  Future<void> updateProfile({
    String? name,
    Map<String, dynamic>? metadata,
  }) async {
    final attributes = UserAttributes(
      data: {
        if (name != null) 'name': name,
        if (metadata != null) ...metadata,
      },
    );
    await _client.auth.updateUser(attributes);
  }

  // Initialize Supabase
  static Future<void> initialize() async {
    await Supabase.initialize(
      url: AppConstants.supabaseUrl,
      anonKey: AppConstants.supabaseAnonKey,
    );
  }
}
