import { BrowserRouter } from 'react-router-dom';

import { AppRoutes } from '@/AppRoutes';
import { AppProviders } from '@/context/AppProviders';

export default function App() {
  return (
    <AppProviders>
      <BrowserRouter>
        <AppRoutes />
      </BrowserRouter>
    </AppProviders>
  );
}
