import 'react-native-get-random-values';
import { AppRegistry } from 'react-native';
import App from './src/app/App';
import { name as appName } from './app.json';

console.log('Happy developing ✨')

AppRegistry.registerComponent(appName, () => App);