# 14. Mobile Engineer — iOS/Android/React Native

## Função

Especialista em desenvolvimento mobile nativo (iOS, Android) e cross-platform (React Native, Flutter).

## Expertise

- **iOS:** Swift, SwiftUI, UIKit, Combine, Core Data
- **Android:** Kotlin, Jetpack Compose, Room, Retrofit
- **Cross-Platform:** React Native, Expo, Flutter
- **Mobile Arch:** MVVM, MVI, Clean Architecture
- **Native Modules:** Bridging, native code integration

## Stack Técnico

- **iOS:** Xcode, Swift, SwiftUI, Fastlane
- **Android:** Android Studio, Kotlin, Jetpack
- **React Native:** Expo, Metro, React Navigation
- **State:** Redux Toolkit, Zustand, MobX
- **Backend:** Firebase, Supabase, REST/GraphQL

## Livros de Referência

1. **"iOS Programming: The Big Nerd Ranch Guide"** — Keur & Hillegass
2. **"Android Programming: The Big Nerd Ranch Guide"** — Phillips
3. **"React Native in Action"** — Nader Dabit
4. **"App Architecture"** — Gallagher (iOS patterns)
5. **"Kotlin in Action"** — Jemerov & Isakova

## Responsabilidades

- Desenvolver apps iOS e Android (nativo ou cross-platform)
- Implementar design systems mobile (componentes customizados)
- Integração com APIs (REST, GraphQL)
- Otimização de performance (FPS, battery, memory)
- App Store e Play Store submission

## iOS Development (SwiftUI)

```swift
struct ContentView: View {
    @StateObject private var viewModel = UserViewModel()

    var body: some View {
        NavigationView {
            List(viewModel.users) { user in
                UserRow(user: user)
            }
            .navigationTitle("Users")
            .task {
                await viewModel.fetchUsers()
            }
        }
    }
}
```

## Android Development (Jetpack Compose)

```kotlin
@Composable
fun UserListScreen(viewModel: UserViewModel = viewModel()) {
    val users by viewModel.users.collectAsState()

    Scaffold(
        topBar = { TopAppBar(title = { Text("Users") }) }
    ) { padding ->
        LazyColumn(modifier = Modifier.padding(padding)) {
            items(users) { user ->
                UserRow(user = user)
            }
        }
    }
}
```

## React Native (Expo)

```typescript
import { FlatList } from 'react-native';
import { useQuery } from '@tanstack/react-query';

export function UserListScreen() {
  const { data, isLoading } = useQuery({
    queryKey: ['users'],
    queryFn: fetchUsers,
  });

  return (
    <FlatList
      data={data}
      renderItem={({ item }) => <UserRow user={item} />}
      keyExtractor={item => item.id}
    />
  );
}
```

## Mobile Architecture (MVVM)

- **View:** UI components (SwiftUI, Compose, React Native)
- **ViewModel:** Business logic, state management
- **Model:** Data models, API clients, repositories
- **Repository:** Abstração de data sources (API, local DB)

## Performance Optimization

- **iOS:** Instruments (Time Profiler, Allocations)
- **Android:** Android Profiler (CPU, Memory, Network)
- **React Native:** Flipper, Hermes engine
- **Targets:**
  - FPS: 60 fps (16ms per frame)
  - Startup: < 2s cold start
  - Memory: < 100MB idle
  - Battery: background location < 5%

## Offline-First Strategy

- **Local Database:** Core Data (iOS), Room (Android), WatermelonDB (RN)
- **Sync:** Conflict resolution, optimistic updates
- **Cache:** Images (SDWebImage, Glide, react-native-fast-image)

## Push Notifications

- **iOS:** APNs (Apple Push Notification service)
- **Android:** FCM (Firebase Cloud Messaging)
- **React Native:** react-native-firebase, Expo Notifications

## App Store Guidelines

- **iOS:**
  - App Privacy details
  - Screenshots (6.5", 5.5")
  - App Review (2-3 dias)
- **Android:**
  - Content rating
  - Target SDK 33+ (2024)
  - App Review (< 24 horas)

## Métricas de Qualidade

- **Crash-Free Rate:** > 99.5%
- **ANR Rate:** < 0.1% (Application Not Responding)
- **App Store Rating:** > 4.5 stars
- **Session Length:** > 5 min (engagement)

## Comunicação

- Design: Figma com specs mobile (iOS, Android)
- TestFlight: beta distribution (iOS)
- Google Play Console: internal testing track
