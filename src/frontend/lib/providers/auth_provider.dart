import 'package:flutter/material.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import '../services/auth_service.dart';

class AuthProvider extends ChangeNotifier {
  final AuthService _authService = AuthService();
  bool _isLoading = false;
  bool _isRestoringSession = true; // Start in restoring state
  String? _error;
  User? _user;

  AuthProvider() {
    _restoreSession();
    _authService.authStateChanges.listen((state) {
      _user = state.session?.user;
      notifyListeners();
    });
  }

  bool get isLoading => _isLoading;
  bool get isRestoringSession => _isRestoringSession;
  String? get error => _error;
  User? get user => _user;
  bool get isLoggedIn => _user != null;
  String? get userId => _user?.id;
  String? get phoneNumber => _user?.phone;

  /// Restore auth session on app restart
  Future<void> _restoreSession() async {
    try {
      final hasSession = await _authService.hasExistingSession();
      if (hasSession) {
        _user = _authService.currentUser;
      }
    } catch (_) {
      // Session restore failed, user stays logged out
    } finally {
      _isRestoringSession = false;
      notifyListeners();
    }
  }

  void setLoading(bool value) {
    _isLoading = value;
    notifyListeners();
  }

  void setError(String? value) {
    _error = value;
    notifyListeners();
  }

  Future<bool> sendOtp(String phoneNumber) async {
    setLoading(true);
    setError(null);
    try {
      await _authService.sendOtp(phoneNumber);
      setLoading(false);
      return true;
    } catch (e) {
      setError(e.toString());
      setLoading(false);
      return false;
    }
  }

  Future<bool> verifyOtp(String phoneNumber, String otp) async {
    setLoading(true);
    setError(null);
    try {
      final response = await _authService.verifyOtp(phoneNumber, otp);
      setLoading(false);
      return response.session != null;
    } catch (e) {
      setError(e.toString());
      setLoading(false);
      return false;
    }
  }

  Future<void> signOut() async {
    setLoading(true);
    try {
      await _authService.signOut();
      _user = null;
    } catch (e) {
      setError(e.toString());
    }
    setLoading(false);
  }

  Future<void> updateProfile({String? name}) async {
    try {
      await _authService.updateProfile(name: name);
    } catch (e) {
      setError(e.toString());
    }
  }
}
