import 'package:flutter/material.dart';

void main() => runApp(const AfriMineApp());

class AfriMineApp extends StatelessWidget {
  const AfriMineApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'AfriMine AI',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xFF2E7D32)),
        useMaterial3: true,
      ),
      home: const HomeScreen(),
    );
  }
}

class HomeScreen extends StatelessWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('AfriMine AI'),
        backgroundColor: const Color(0xFF2E7D32),
        foregroundColor: Colors.white,
      ),
      body: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.landscape, size: 80, color: Colors.amber[700]),
            const SizedBox(height: 16),
            const Text(
              'AfriMine AI',
              style: TextStyle(fontSize: 28, fontWeight: FontWeight.bold),
            ),
            const Text('Know Your Ground', style: TextStyle(fontSize: 16, color: Colors.grey)),
            const SizedBox(height: 32),
            ElevatedButton.icon(
              onPressed: () {},
              icon: const Icon(Icons.camera_alt),
              label: const Text('Capture Sample'),
            ),
          ],
        ),
      ),
    );
  }
}
