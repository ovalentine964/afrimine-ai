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
    try {
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
    } on AuthException catch (e) {
      throw Exception('Authentication error: ${e.message}');
    } catch (e) {
      throw Exception('Failed to send OTP. Please try again.');
    }
  }

  Future<AuthResponse> verifyOtp(String phoneNumber, String otp) async {
    try {
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
    } on AuthException catch (e) {
      throw Exception('Verification failed: ${e.message}');
    } catch (e) {
      throw Exception('Failed to verify OTP. Please try again.');
    }
  }

  Future<void> signOut() async {
    try {
      await _client.auth.signOut();
    } catch (e) {
      throw Exception('Failed to sign out. Please try again.');
    }
  }

  Future<void> updateProfile({
    String? name,
    Map<String, dynamic>? metadata,
  }) async {
    try {
      final attributes = UserAttributes(
        data: {
          if (name != null) 'name': name,
          if (metadata != null) ...metadata,
        },
      );
      await _client.auth.updateUser(attributes);
    } on AuthException catch (e) {
      throw Exception('Profile update failed: ${e.message}');
    } catch (e) {
      throw Exception('Failed to update profile. Please try again.');
    }
  }

  // Check if user has an existing session (for app restart)
  Future<bool> hasExistingSession() async {
    try {
      final session = _client.auth.currentSession;
      if (session == null) return false;
      // Check if session is expired
      if (session.isExpired) {
        // Try to refresh
        final response = await _client.auth.refreshSession();
        return response.session != null;
      }
      return true;
    } catch (e) {
      return false;
    }
  }

  // Initialize Supabase
  static Future<void> initialize() async {
    try {
      await Supabase.initialize(
        url: AppConstants.supabaseUrl,
        anonKey: AppConstants.supabaseAnonKey,
      );
    } catch (e) {
      throw Exception('Failed to initialize authentication service. Please check your connection.');
    }
  }
}
