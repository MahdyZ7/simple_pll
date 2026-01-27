/* ************************************************************************** */
/*                                                                            */
/*                                                        :::      ::::::::   */
/*   Fixed.hpp                                          :+:      :+:    :+:   */
/*                                                    +:+ +:+         +:+     */
/*   By: ayassin <ayassin@student.42abudhabi.ae>    +#+  +:+       +#+        */
/*                                                +#+#+#+#+#+   +#+           */
/*   Created: 2022/09/27 16:09:01 by ayassin           #+#    #+#             */
/*   Updated: 2022/09/29 12:58:05 by ayassin          ###   ########.fr       */
/*                                                                            */
/* ************************************************************************** */

#ifndef FIXED_HPP
#define FIXED_HPP

#include <iostream>
#include <tgmath.h>

template <typename T>
class Fixed{
	public:
		Fixed(void);
		Fixed(const T x);
		Fixed(const float x);
		Fixed(const double x);
		Fixed(const T x, const int frac_size);
		Fixed(const float x, const int frac_size);
		Fixed(const double x, const int frac_size);
		Fixed(Fixed const &src);
		~Fixed(void);

		Fixed<T> &operator=(Fixed<T> const &cpy);
		Fixed<T> operator+(Fixed<T> const &alu);
		Fixed<T> operator-(Fixed<T> const &alu);
		Fixed<T> operator*(Fixed<T> const &alu);
		Fixed<T> operator/(Fixed<T> const &alu);
		Fixed<T> &operator++(); //prefix
		Fixed<T> operator++(int); //postfix
		Fixed<T> &operator--(); //prefix
		Fixed<T> operator--(int); //postfix
		bool operator>(Fixed<T> const &cpy) const;
		bool operator>=(Fixed<T> const &cpy) const;
		bool operator<(Fixed<T> const &cpy) const;
		bool operator<=(Fixed<T> const &cpy) const;
		bool operator==(Fixed<T> const &cpy) const;
		bool operator!=(Fixed<T> const &cpy) const;

		int		getFixedBits( void ) const;
		void	setFixedBits( int const raw );
		T	getRawBits( void ) const;
		void	setRawBits( T const raw );
		float	toFloat(void) const;
		int		toInt(void) const;
		long	toLong(void) const;
		double	toDouble(void) const;


		static Fixed<T>	max(Fixed<T> const &a, Fixed<T> const &b);
		static Fixed<T>	min(Fixed<T> const &a, Fixed<T> const &b);
		private:
			T num;
			int frac;
};

// Template implementation

template <typename T>
Fixed<T>::Fixed(void):num(0), frac(8)
{
}

template <typename T>
Fixed<T>::Fixed(const T x):frac(8)
{
	num = x << frac;
	if (x < 0)
		num = num | 0x80000000;
	else
		num =  num & 0x7fffffff;
}

template <typename T>
Fixed<T>::Fixed(const float x):frac(8)
{
	T one = 1;
	num = 0;
	num = num | ((T) roundf(x * (one << frac)));
}

template <typename T>
Fixed<T>::Fixed(const double x):frac(8)
{
	num = 0;
	T one = 1;
	num = num | ((T) roundf(x * (one << frac)));
}

template <typename T>
Fixed<T>::Fixed(const T x, const int frac_size):frac(frac_size)
{
	num = x << frac;
	if (x < 0)
		num = num | 0x80000000;
	else
		num =  num & 0x7fffffff;
}

template <typename T>
Fixed<T>::Fixed(const float x, const int frac_size):frac(frac_size)
{
	num = 0;
	T one = 1;
	num = num | ((T) roundf(x * (one << frac)));
}

template <typename T>
Fixed<T>::Fixed(const double x, const int frac_size):frac(frac_size)
{
	num = 0;
	T one = 1;
	num = num | ((T) roundf(x * (one << frac)));
}

template <typename T>
Fixed<T>::Fixed(Fixed const &src)
{
	*this = src;
}

template <typename T>
Fixed<T>::~Fixed(void)
{
}

template <typename T>
Fixed<T> &Fixed<T>::operator=(Fixed const &cpy)
{
	this->frac = cpy.frac;
	this->num = cpy.num;
	return (*this);
}

template <typename T>
int	Fixed<T>::getFixedBits( void ) const
{
	return (frac);
}

template <typename T>
void	Fixed<T>::setFixedBits( int const frac_size )
{
	frac = frac_size;
}

template <typename T>
T	Fixed<T>::getRawBits(void) const
{
	return(num);
}

template <typename T>
void Fixed<T>::setRawBits(T const raw)
{
	num = raw;
}

template <typename T>
float Fixed<T>::toFloat(void) const
{
	return(float (num) / float (1u << frac));
}

template <typename T>
double Fixed<T>::toDouble(void) const
{
	return(double (num) / double (1u << frac));
}

template <typename T>
int Fixed<T>::toInt(void) const
{
	T one = 1;
	T two = 2;
	return((num >> frac) + ((num & ((two << frac) - one)) && (num < 0)));
}

template <typename T>
long Fixed<T>::toLong(void) const
{
	T one = 1;
	T two = 2;
	return((num >> frac) + ((num & ((two << frac) - one)) && (num < 0)));
}

template <typename T>
std::ostream& operator<<(std::ostream &os, Fixed<T> const &n)
{
	os << n.toFloat();
	return (os);
}

//***********************************
//		compare operators			*
//***********************************

template <typename T>
bool Fixed<T>::operator>(Fixed<T> const &cpy)  const
{
	if (this->num > cpy.num)
		return (true);
	return(false);
}

template <typename T>
bool Fixed<T>::operator>=(Fixed<T> const &cpy)  const
{
	if (this->num >= cpy.num)
		return (true);
	return(false);
}

template <typename T>
bool Fixed<T>::operator<(Fixed<T> const &cpy)  const
{
	if (this->num < cpy.num)
		return (true);
	return(false);
}

template <typename T>
bool Fixed<T>::operator<=(Fixed<T> const &cpy)  const
{
	if (this->num <= cpy.num)
		return (true);
	return(false);
}

template <typename T>
bool Fixed<T>::operator==(Fixed<T> const &cpy)  const
{
	if (this->num == cpy.num)
		return (true);
	return(false);
}

template <typename T>
bool Fixed<T>::operator!=(Fixed<T> const &cpy)  const
{
	if (this->num != cpy.num)
		return (true);
	return(false);
}

//***********************************
//				operators			*
//***********************************

template <typename T>
Fixed<T> &Fixed<T>::operator++() //prefix
{
	++num;
	return (*this);
}

template <typename T>
Fixed<T> Fixed<T>::operator++(int) //postfix
{
	Fixed<T> temp((T) 0, this->frac);
	temp.num = num++;
	return (temp);
}

template <typename T>
Fixed<T> &Fixed<T>::operator--() //prefix
{
	--num;
	return (*this);
}

template <typename T>
Fixed<T> Fixed<T>::operator--(int) //postfix
{
	Fixed<T> temp((T) 0, this->frac);
	temp.num = num--;
	return (temp);
}

template <typename T>
Fixed<T> Fixed<T>::operator+(Fixed<T> const &alu)
{
	Fixed<T> temp((T) 0, this->frac);
	temp.num = this->num + alu.num;
	return (temp);
}

template <typename T>
Fixed<T> Fixed<T>::operator-(Fixed<T> const &alu)
{
	Fixed<T> temp((T) 0, this->frac);
	temp.num = this->num - alu.num;
	return (temp);
}

template <typename T>
Fixed<T> Fixed<T>::operator*(Fixed<T> const &alu)
{
	Fixed<T> temp((T) 0, this->frac);
	T prod = T (this->num) * T (alu.num);
	temp.num = prod >> frac;
	return (temp);
}

template <typename T>
Fixed<T> Fixed<T>::operator/(Fixed<T> const &alu)
{
	Fixed<T> temp((T) 0, this->frac);
	temp.num = T (this->num) * (1 << 24) / (T (alu.num) * (1 << 16));
	return (temp);
}

// non member functions

template <typename T>
Fixed<T> Fixed<T>::max(Fixed<T> const &a, Fixed<T> const &b)
{
	if (a > b)
		return (a);
	return (b);
}

template <typename T>
Fixed<T> Fixed<T>::min(Fixed<T> const &a, Fixed<T> const &b)
{
	if (a < b)
		return (a);
	return(b);
}

#endif 