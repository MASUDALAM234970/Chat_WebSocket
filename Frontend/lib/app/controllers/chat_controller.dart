import 'package:get/get.dart';
import '../models/message_model.dart';
import '../services/api_service.dart';

class ChatController extends GetxController {
  var messages   = <MessageModel>[].obs;
  var isLoading  = false.obs;
  var history    = <Map<String, String>>[];

  Future<void> sendMessage(String userText) async {
    if (userText.trim().isEmpty) return;


    messages.add(MessageModel(content: userText, isUser: true));

    isLoading.value = true;


    final reply = await ApiService.sendMessage(userText, history);


    messages.add(MessageModel(content: reply, isUser: false));


    history.add({'role': 'user',      'content': userText});
    history.add({'role': 'assistant', 'content': reply});


    if (history.length > 10) {
      history = history.sublist(history.length - 10);
    }

    isLoading.value = false;
  }

  void clearChat() {
    messages.clear();
    history.clear();
  }
}