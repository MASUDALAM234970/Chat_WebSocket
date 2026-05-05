import 'package:flutter/material.dart';
import 'package:get/get.dart';

import 'app/bindings/chat_binding.dart';
import 'app/views/chat_view.dart';

void main() {
  runApp(const MyApp());
}

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return GetMaterialApp(
      title: 'AI Chatbot',
      debugShowCheckedModeBanner: false,
      theme: ThemeData.dark(),
      initialBinding: ChatBinding(),
      home: ChatView(),
    );
  }
}