export type UserRole = "member" | "manager" | "admin";

export interface MeUser {
  id: number;
  email: string;
  full_name: string;
  phone: string;
  document: string | null;
  role: UserRole;
}

export interface GearItem {
  id: number;
  name: string;
  total_quantity: number;
  available_count: number;
  description: string | null;
}

export interface GearSearchResponse {
  items: GearItem[];
}

export interface RentalRequestItem {
  gear_id: number;
  qty_requested: number;
}

export interface RentalRequest {
  id: number;
  user_id: number;
  user_full_name: string;
  target_manager_id: number | null;
  status: string;
  created_at: string;
  due_date: string;
  event: string;
  comment: string | null;
  deposit_document: string | null;
  decision_comment: string | null;
  items: RentalRequestItem[];
}

export interface RentalRequestsList {
  requests: RentalRequest[];
}

export interface RentalItemOut {
  gear_id: number;
  gear_name: string;
  qty_issued: number;
  qty_outstanding: number;
}

export interface Rental {
  id: number;
  user_id: number;
  user_full_name: string;
  issue_manager_id: number;
  issue_date: string;
  due_date: string;
  event: string;
  comment: string | null;
  status: string;
  closed_at: string | null;
  items: RentalItemOut[];
}

export interface RentalsList {
  rentals: Rental[];
}

export interface ReturnRequestItem {
  gear_id: number;
  qty_return: number;
}

export interface RentalReturnRequest {
  id: number;
  user_id: number;
  user_full_name: string;
  rental_id: number;
  target_manager_id: number | null;
  status: string;
  created_at: string;
  decision_comment: string | null;
  items: ReturnRequestItem[];
}

export interface RentalReturnRequestsList {
  requests: RentalReturnRequest[];
}

export interface AdminUser {
  id: number;
  email: string;
  full_name: string;
  phone: string;
  document: string | null;
  role: UserRole;
  is_active: boolean;
}

export interface AdminUserList {
  users: AdminUser[];
}
