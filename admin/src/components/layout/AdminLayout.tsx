import { Avatar, Box, Button, Flex, HStack, Icon, Link, Stack, Text } from '@chakra-ui/react';
import { Suspense, useState } from 'react';
import type { IconType } from 'react-icons';
import { FiBookOpen, FiFilm, FiGrid, FiHelpCircle, FiLogOut, FiUsers } from 'react-icons/fi';
import { NavLink, Outlet } from 'react-router-dom';

import { LoadingState } from '@/components/ui/LoadingState';
import { useAuth } from '@/hooks/useAuth';

interface NavItem {
  label: string;
  to: string;
  icon: IconType;
  /** Match the path exactly (used for the dashboard index route). */
  end?: boolean;
}

const NAV_ITEMS: readonly NavItem[] = [
  { label: 'Dashboard', to: '/admin', icon: FiGrid, end: true },
  { label: 'Curriculum', to: '/admin/curriculum', icon: FiBookOpen },
  { label: 'Content', to: '/admin/content', icon: FiFilm },
  { label: 'Questions', to: '/admin/questions', icon: FiHelpCircle },
  { label: 'Users', to: '/admin/users', icon: FiUsers },
];

interface SidebarLinkProps {
  item: NavItem;
}

function SidebarLink({ item }: SidebarLinkProps) {
  return (
    <Link
      asChild
      display="flex"
      alignItems="center"
      gap={3}
      px={3}
      py={2}
      borderRadius="md"
      color="fgMuted"
      fontWeight="medium"
      whiteSpace="nowrap"
      textDecoration="none"
      transition="background-color 0.15s ease, color 0.15s ease"
      _hover={{ bg: 'bg', color: 'fg', textDecoration: 'none' }}
      _currentPage={{ bg: 'primary.subtle', color: 'primary' }}
    >
      <NavLink to={item.to} end={item.end}>
        <Icon as={item.icon} boxSize={4} />
        {item.label}
      </NavLink>
    </Link>
  );
}

export function AdminLayout() {
  const { user, signOut } = useAuth();
  const [signingOut, setSigningOut] = useState(false);
  const displayName = user?.fullName ?? user?.email ?? 'Admin';

  const handleSignOut = async (): Promise<void> => {
    setSigningOut(true);
    try {
      await signOut();
    } finally {
      setSigningOut(false);
    }
  };

  return (
    <Flex minH="100vh" bg="bg" direction={{ base: 'column', md: 'row' }}>
      <Box
        as="nav"
        aria-label="Admin navigation"
        bg="surface"
        borderColor="border"
        borderBottomWidth={{ base: '1px', md: 0 }}
        borderRightWidth={{ base: 0, md: '1px' }}
        w={{ base: 'full', md: '240px' }}
        flexShrink={0}
        px={{ base: 4, md: 4 }}
        py={{ base: 3, md: 6 }}
      >
        <Text
          fontWeight="bold"
          color="fg"
          fontSize="md"
          mb={{ base: 3, md: 8 }}
          px={{ base: 0, md: 3 }}
        >
          Teacher Assistant
          <Text as="span" display="block" fontSize="xs" fontWeight="medium" color="fgMuted">
            Admin panel
          </Text>
        </Text>
        <Stack
          direction={{ base: 'row', md: 'column' }}
          gap={1}
          overflowX={{ base: 'auto', md: 'visible' }}
        >
          {NAV_ITEMS.map((item) => (
            <SidebarLink key={item.to} item={item} />
          ))}
        </Stack>
      </Box>

      <Flex direction="column" flex="1" minW={0}>
        <Flex
          as="header"
          justify="flex-end"
          align="center"
          gap={4}
          px={{ base: 4, md: 8 }}
          py={3}
          bg="surface"
          borderBottomWidth="1px"
          borderColor="border"
        >
          <HStack gap={3} minW={0}>
            <Avatar.Root size="sm" bg="primary.subtle" color="primary">
              <Avatar.Fallback name={displayName} />
              {user?.avatarUrl && <Avatar.Image src={user.avatarUrl} alt="" />}
            </Avatar.Root>
            <Box minW={0} display={{ base: 'none', sm: 'block' }}>
              <Text fontSize="sm" fontWeight="medium" color="fg" truncate>
                {displayName}
              </Text>
              {user?.fullName && (
                <Text fontSize="xs" color="fgMuted" truncate>
                  {user.email}
                </Text>
              )}
            </Box>
          </HStack>
          <Button
            size="sm"
            variant="outline"
            borderColor="border"
            color="fg"
            _hover={{ bg: 'bg' }}
            onClick={() => void handleSignOut()}
            loading={signingOut}
          >
            <Icon as={FiLogOut} />
            Log out
          </Button>
        </Flex>

        <Box as="main" flex="1" px={{ base: 4, md: 8 }} py={{ base: 6, md: 8 }}>
          <Suspense fallback={<LoadingState />}>
            <Outlet />
          </Suspense>
        </Box>
      </Flex>
    </Flex>
  );
}
