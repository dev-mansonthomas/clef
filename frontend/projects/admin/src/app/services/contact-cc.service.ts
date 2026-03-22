import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import {
  ContactCC,
  ContactCCListResponse,
  CreateContactCCRequest,
  UpdateContactCCRequest,
} from '../models/repair.model';
import { environment } from '../../environments/environment';

@Injectable({
  providedIn: 'root'
})
export class ContactCCService {
  private readonly apiUrl = environment.apiUrl;

  constructor(private http: HttpClient) {}

  /**
   * List contacts CC for a DT (includes DT-level + user's UL-level)
   */
  listContactsCC(dt: string): Observable<ContactCCListResponse> {
    return this.http.get<ContactCCListResponse>(`${this.apiUrl}/api/${dt}/contacts-cc`, {
      withCredentials: true,
    });
  }

  /**
   * Create a new contact CC
   */
  createContactCC(dt: string, data: CreateContactCCRequest): Observable<ContactCC> {
    return this.http.post<ContactCC>(`${this.apiUrl}/api/${dt}/contacts-cc`, data, {
      withCredentials: true,
    });
  }

  /**
   * Update an existing contact CC
   */
  updateContactCC(dt: string, id: string, data: UpdateContactCCRequest): Observable<ContactCC> {
    return this.http.patch<ContactCC>(`${this.apiUrl}/api/${dt}/contacts-cc/${id}`, data, {
      withCredentials: true,
    });
  }
}

