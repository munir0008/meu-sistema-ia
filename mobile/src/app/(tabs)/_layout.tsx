import { Ionicons } from "@expo/vector-icons";
import { Tabs } from "expo-router";

export default function TabsLayout() {
  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: "#f97316",
      }}
    >
      <Tabs.Screen
        name="dashboard"
        options={{
          title: "Dashboard",
          tabBarIcon: ({ color, size }) => <Ionicons name="stats-chart" color={color} size={size} />,
        }}
      />
      <Tabs.Screen
        name="cameras"
        options={{
          title: "Câmeras",
          tabBarIcon: ({ color, size }) => <Ionicons name="videocam" color={color} size={size} />,
        }}
      />
      <Tabs.Screen
        name="assinatura"
        options={{
          title: "Assinatura",
          tabBarIcon: ({ color, size }) => <Ionicons name="card" color={color} size={size} />,
        }}
      />
    </Tabs>
  );
}
