from django.http import HttpResponse

from zerver.lib.actions import (
    do_change_stream_web_public,
    do_deactivate_stream,
    get_web_public_streams,
    get_web_public_subs,
)
from zerver.lib.test_classes import ZulipTestCase
from zerver.models import get_realm


class GlobalPublicStreamTest(ZulipTestCase):
    def test_non_existant_stream_id(self) -> None:
        # Here we use a relatively big number as stream id assuming such an id
        # won't exist in the test DB.
        result = self.client_get("/archive/streams/100000000/topics/TopicGlobal")
        self.assert_in_success_response(["This stream does not exist."], result)

    def test_non_web_public_stream(self) -> None:
        test_stream = self.make_stream("Test Public Archives")
        result = self.client_get(
            "/archive/streams/" + str(test_stream.id) + "/topics/notpublicglobalstream",
        )
        self.assert_in_success_response(["This stream does not exist."], result)

    def test_non_existant_topic(self) -> None:
        test_stream = self.make_stream("Test Public Archives")
        do_change_stream_web_public(test_stream, True)
        result = self.client_get(
            "/archive/streams/" + str(test_stream.id) + "/topics/nonexistenttopic",
        )
        self.assert_in_success_response(["This topic does not exist."], result)

    def test_web_public_stream_topic(self) -> None:
        test_stream = self.make_stream("Test Public Archives")
        do_change_stream_web_public(test_stream, True)

        def send_msg_and_get_result(msg: str) -> HttpResponse:
            self.send_stream_message(
                self.example_user("iago"),
                "Test Public Archives",
                msg,
                "TopicGlobal",
            )
            return self.client_get(
                "/archive/streams/" + str(test_stream.id) + "/topics/TopicGlobal",
            )

        result = send_msg_and_get_result("Test Message 1")
        self.assert_in_success_response(["Test Message 1"], result)
        result = send_msg_and_get_result("/me goes testing.")
        self.assert_in_success_response(["goes testing."], result)

    def test_get_web_public_streams(self) -> None:
        realm = get_realm("zulip")
        public_streams = get_web_public_streams(realm)
        self.assert_length(public_streams, 1)
        public_stream = public_streams[0]
        self.assertEqual(public_stream["name"], "Rome")

        info = get_web_public_subs(realm)
        self.assert_length(info.subscriptions, 1)
        self.assertEqual(info.subscriptions[0]["name"], "Rome")
        self.assert_length(info.unsubscribed, 0)
        self.assert_length(info.never_subscribed, 0)

        # Now add a second public stream
        test_stream = self.make_stream("Test Public Archives")
        do_change_stream_web_public(test_stream, True)
        public_streams = get_web_public_streams(realm)
        self.assert_length(public_streams, 2)
        info = get_web_public_subs(realm)
        self.assert_length(info.subscriptions, 2)
        self.assert_length(info.unsubscribed, 0)
        self.assert_length(info.never_subscribed, 0)
        self.assertNotEqual(info.subscriptions[0]["color"], info.subscriptions[1]["color"])

        do_deactivate_stream(test_stream, acting_user=None)
        public_streams = get_web_public_streams(realm)
        self.assert_length(public_streams, 1)
        info = get_web_public_subs(realm)
        self.assert_length(info.subscriptions, 1)
        self.assert_length(info.unsubscribed, 0)
        self.assert_length(info.never_subscribed, 0)


class WebPublicTopicHistoryTest(ZulipTestCase):
    def test_non_existant_stream_id(self) -> None:
        result = self.client_get("/archive/streams/100000000/topics")
        self.assert_json_success(result)
        history = result.json()["topics"]
        self.assertEqual(history, [])

    def test_non_web_public_stream(self) -> None:
        test_stream = self.make_stream("Test Public Archives")

        self.send_stream_message(
            self.example_user("iago"),
            "Test Public Archives",
            "Test Message",
            "TopicGlobal",
        )

        result = self.client_get(
            "/archive/streams/" + str(test_stream.id) + "/topics",
        )
        self.assert_json_success(result)
        history = result.json()["topics"]
        self.assertEqual(history, [])

    def test_web_public_stream(self) -> None:
        test_stream = self.make_stream("Test Public Archives")
        do_change_stream_web_public(test_stream, True)

        self.send_stream_message(
            self.example_user("iago"),
            "Test Public Archives",
            "Test Message 3",
            topic_name="first_topic",
        )
        self.send_stream_message(
            self.example_user("iago"),
            "Test Public Archives",
            "Test Message",
            topic_name="TopicGlobal",
        )
        self.send_stream_message(
            self.example_user("iago"),
            "Test Public Archives",
            "Test Message 2",
            topic_name="topicglobal",
        )
        self.send_stream_message(
            self.example_user("iago"),
            "Test Public Archives",
            "Test Message 3",
            topic_name="second_topic",
        )
        self.send_stream_message(
            self.example_user("iago"),
            "Test Public Archives",
            "Test Message 4",
            topic_name="TopicGlobal",
        )

        result = self.client_get(
            "/archive/streams/" + str(test_stream.id) + "/topics",
        )
        self.assert_json_success(result)
        history = result.json()["topics"]
        self.assert_length(history, 3)
        # Should be sorted with latest topic first
        self.assertEqual(history[0]["name"], "TopicGlobal")
        self.assertEqual(history[1]["name"], "second_topic")
        self.assertEqual(history[2]["name"], "first_topic")
